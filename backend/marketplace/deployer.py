"""
工具市场部署执行器
- Docker Compose：通过 SSH 上传 docker-compose.yml 并执行远程命令
- Kubernetes：调用 kubernetes Python SDK 将 YAML 资源下发到目标集群
"""
import logging
import re

import paramiko
import yaml
from django.db import close_old_connections
from django.utils.text import slugify
from kubernetes import utils as k8s_utils
from kubernetes.client.exceptions import ApiException

from eventwall.models import EventRecord
from eventwall.services import build_resource, record_event
from ops.k8s_views import _get_k8s_client, _is_demo

from .models import ServiceDeployment

logger = logging.getLogger(__name__)

DEPLOY_BASE = '/opt/sxdevops'


def _render_template(template_str, context):
    """简易模板渲染：将 {{key}} 替换为 context[key]"""
    result = template_str or ''
    for key, value in context.items():
        result = result.replace('{{' + key + '}}', str(value))
    return re.sub(r'\{\{[^}]+\}\}', '', result)


def _service_slug(template_name):
    return slugify(template_name) or re.sub(r'[^a-z0-9]+', '-', template_name.lower()).strip('-') or 'service'


def _related_resources(deployment):
    related = [build_resource('marketplace', 'service_template', deployment.template_id, deployment.template.name)]
    if deployment.host_id:
        related.append(build_resource('ops', 'host', deployment.host_id, deployment.host.hostname))
    if deployment.cluster_id:
        related.append(build_resource('ops', 'k8s_cluster', deployment.cluster_id, deployment.cluster.name))
    return related


def _get_ssh_client(host):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host.ip_address,
        port=getattr(host, 'ssh_port', 22) or 22,
        username=getattr(host, 'ssh_user', 'root') or 'root',
        password=getattr(host, 'ssh_password', '') or None,
        timeout=15,
    )
    return client


def _ssh_exec(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return exit_code, out, err


def _k8s_common_labels(deployment):
    return {
        'app.kubernetes.io/managed-by': 'sxdevops',
        'app.kubernetes.io/instance': deployment.release_name,
        'app.kubernetes.io/name': _service_slug(deployment.template.name),
    }


def _k8s_label_selector(deployment):
    labels = _k8s_common_labels(deployment)
    return ','.join(f'{key}={value}' for key, value in labels.items())


def _inject_pod_labels(spec, labels):
    if not isinstance(spec, dict):
        return
    template = spec.get('template')
    if not isinstance(template, dict):
        return

    template_meta = template.setdefault('metadata', {})
    template_labels = template_meta.setdefault('labels', {})
    template_labels.update(labels)

    selector = spec.setdefault('selector', {})
    if isinstance(selector, dict):
        match_labels = selector.setdefault('matchLabels', {})
        match_labels.update(labels)


def _prepare_k8s_documents(manifest_content, deployment):
    labels = _k8s_common_labels(deployment)
    documents = []

    for document in yaml.safe_load_all(manifest_content):
        if not isinstance(document, dict):
            continue

        kind = document.get('kind')
        metadata = document.setdefault('metadata', {})
        if kind != 'Namespace':
            metadata.setdefault('namespace', deployment.namespace or 'default')
        metadata.setdefault('labels', {}).update(labels)

        spec = document.get('spec')
        if kind in {'Deployment', 'StatefulSet', 'DaemonSet', 'Job'}:
            _inject_pod_labels(spec, labels)
        elif kind == 'CronJob' and isinstance(spec, dict):
            job_template = spec.get('jobTemplate', {})
            job_spec = job_template.get('spec', {}) if isinstance(job_template, dict) else {}
            _inject_pod_labels(job_spec, labels)
        elif kind == 'Service' and isinstance(spec, dict):
            selector = spec.setdefault('selector', {})
            if isinstance(selector, dict):
                selector.update(labels)

        documents.append(document)

    return documents


def _ensure_k8s_namespace(client_module, namespace):
    namespace = namespace or 'default'
    v1 = client_module.CoreV1Api()
    try:
        v1.read_namespace(namespace)
        return False
    except ApiException as exc:
        if exc.status != 404:
            raise

    namespace_body = client_module.V1Namespace(
        metadata=client_module.V1ObjectMeta(
            name=namespace,
            labels={'app.kubernetes.io/managed-by': 'sxdevops'},
        )
    )
    v1.create_namespace(namespace_body)
    return True


def _select_k8s_pod(pods):
    if not pods:
        return None
    return sorted(
        pods,
        key=lambda pod: (
            getattr(getattr(pod, 'status', None), 'phase', '') != 'Running',
            getattr(getattr(pod, 'metadata', None), 'name', ''),
        ),
    )[0]


def _deploy_docker_compose(deployment, log_lines):
    template = deployment.template
    host = deployment.host
    service_dir = f'{DEPLOY_BASE}/{_service_slug(template.name)}'
    deployment.deploy_dir = service_dir
    deployment.save(update_fields=['deploy_dir'])

    context = {'version': deployment.version}
    context.update(deployment.env_config)
    compose_content = _render_template(template.docker_compose_template, context)

    client = _get_ssh_client(host)
    try:
        log_lines.append(f'[✓] SSH 连接成功: {host.ip_address}:{getattr(host, "ssh_port", 22)}')

        _ssh_exec(client, f'mkdir -p {service_dir}')
        log_lines.append(f'[✓] 创建目录: {service_dir}')

        sftp = client.open_sftp()
        compose_path = f'{service_dir}/docker-compose.yml'
        with sftp.file(compose_path, 'w') as file_obj:
            file_obj.write(compose_content)
        sftp.close()
        log_lines.append('[✓] 上传 docker-compose.yml')

        code, out, err = _ssh_exec(
            client,
            f'cd {service_dir} && docker-compose up -d 2>&1 || docker compose up -d 2>&1',
        )
        log_lines.append('[CMD] docker-compose up -d')
        if out.strip():
            log_lines.append(out.strip())
        if err.strip():
            log_lines.append(err.strip())

        if code != 0:
            raise RuntimeError(f'docker-compose 执行失败，退出码: {code}')
    finally:
        client.close()


def _deploy_k8s(deployment, log_lines):
    cluster = deployment.cluster
    namespace = deployment.namespace or 'default'
    release_name = deployment.release_name or _service_slug(deployment.template.name)
    deployment.release_name = release_name
    deployment.deploy_dir = f'k8s://{cluster.name}/{namespace}/{release_name}'
    deployment.save(update_fields=['release_name', 'deploy_dir'])

    if _is_demo(cluster):
        log_lines.extend([
            f'[✓] 已连接 Demo K8s 集群: {cluster.name}',
            f'[✓] 命名空间: {namespace}',
            f'[✓] 发布名称: {release_name}',
            '[✓] Demo 模式已模拟创建 Deployment/Service 资源',
        ])
        return

    context = {
        'version': deployment.version,
        'namespace': namespace,
        'release_name': release_name,
        'replicas': deployment.replicas,
    }
    context.update(deployment.env_config)
    manifest_content = _render_template(deployment.template.k8s_manifest_template, context)
    documents = _prepare_k8s_documents(manifest_content, deployment)
    if not documents:
        raise RuntimeError('K8s YAML 模板为空，未生成任何资源')

    client_module = _get_k8s_client(cluster)
    if _ensure_k8s_namespace(client_module, namespace):
        log_lines.append(f'[✓] 已创建命名空间: {namespace}')
    else:
        log_lines.append(f'[✓] 使用现有命名空间: {namespace}')

    api_client = client_module.ApiClient()
    for document in documents:
        kind = document.get('kind', 'Unknown')
        name = document.get('metadata', {}).get('name', '-')
        k8s_utils.create_from_dict(api_client, document, namespace=namespace, verbose=False)
        log_lines.append(f'[✓] 已创建 {kind}/{name}')


def _scale_k8s_workloads(deployment, replicas):
    cluster = deployment.cluster
    if _is_demo(cluster):
        return [f'DemoWorkload/{deployment.release_name or _service_slug(deployment.template.name)}']

    client_module = _get_k8s_client(cluster)
    apps_v1 = client_module.AppsV1Api()
    selector = _k8s_label_selector(deployment)
    namespace = deployment.namespace or 'default'
    body = {'spec': {'replicas': replicas}}
    scaled = []

    for item in apps_v1.list_namespaced_deployment(namespace, label_selector=selector).items:
        apps_v1.patch_namespaced_deployment_scale(item.metadata.name, namespace, body)
        scaled.append(f'Deployment/{item.metadata.name}')

    for item in apps_v1.list_namespaced_stateful_set(namespace, label_selector=selector).items:
        apps_v1.patch_namespaced_stateful_set_scale(item.metadata.name, namespace, body)
        scaled.append(f'StatefulSet/{item.metadata.name}')

    return scaled


def deploy_service(deployment_id):
    """????????"""
    close_old_connections()

    try:
        deployment = ServiceDeployment.objects.select_related('template', 'host', 'cluster').get(pk=deployment_id)
    except ServiceDeployment.DoesNotExist:
        logger.error('Deployment %s not found', deployment_id)
        return

    deployment.status = 'deploying'
    deployment.deploy_log = ''
    deployment.save(update_fields=['status', 'deploy_log'])
    log_lines = [f'[INFO] ????: {deployment.get_deploy_mode_display()}']
    try:
        if deployment.deploy_mode == 'k8s':
            _deploy_k8s(deployment, log_lines)
        else:
            _deploy_docker_compose(deployment, log_lines)
        deployment.status = 'running'
        log_lines.append('[SUCCESS] ????')
        record_event(
            module='marketplace',
            category='execution',
            action='deploy_finish',
            title='????????',
            summary=f'?? {deployment.template.name} ????',
            result=EventRecord.RESULT_SUCCESS,
            source_type=EventRecord.SOURCE_ASYNC,
            actor_type=EventRecord.ACTOR_SYSTEM,
            actor_username=deployment.deployer or 'system',
            actor_display=deployment.deployer or 'system',
            resource_type='service_deployment',
            resource_id=deployment.id,
            resource_name=deployment.template.name,
            application=deployment.template.name,
            correlation_id=f'marketplace-deployment:{deployment.id}',
            related_resources=_related_resources(deployment),
            metadata={'deploy_mode': deployment.deploy_mode, 'version': deployment.version},
        )
    except Exception as exc:
        deployment.status = 'failed'
        log_lines.append(f'[ERROR] ????: {str(exc)}')
        logger.exception('deploy_service error')
        record_event(
            module='marketplace',
            category='execution',
            action='deploy_finish',
            title='????????',
            summary=f'?? {deployment.template.name} ????',
            result=EventRecord.RESULT_FAILED,
            severity=EventRecord.SEVERITY_WARNING,
            source_type=EventRecord.SOURCE_ASYNC,
            actor_type=EventRecord.ACTOR_SYSTEM,
            actor_username=deployment.deployer or 'system',
            actor_display=deployment.deployer or 'system',
            resource_type='service_deployment',
            resource_id=deployment.id,
            resource_name=deployment.template.name,
            application=deployment.template.name,
            correlation_id=f'marketplace-deployment:{deployment.id}',
            related_resources=_related_resources(deployment),
            metadata={'deploy_mode': deployment.deploy_mode, 'version': deployment.version, 'error': str(exc)},
        )

    deployment.deploy_log = '\n'.join(log_lines)
    deployment.save(update_fields=['status', 'deploy_log'])
    close_old_connections()
    return deployment


def stop_service(deployment):
    """停止服务"""
    if deployment.deploy_mode == 'k8s':
        try:
            scaled = _scale_k8s_workloads(deployment, 0)
            if not scaled:
                raise RuntimeError('未找到可停止的 K8s 工作负载')
            deployment.status = 'stopped'
            deployment.deploy_log += f'\n[✓] 已缩容到 0 副本: {", ".join(scaled)}'
        except Exception as exc:
            deployment.deploy_log += f'\n[✗] 停止失败: {str(exc)}'
        deployment.save(update_fields=['status', 'deploy_log'])
        return deployment

    host = deployment.host
    service_dir = deployment.deploy_dir
    if not service_dir:
        deployment.deploy_log += '\n[✗] 无部署目录信息，无法停止'
        deployment.save(update_fields=['deploy_log'])
        return deployment

    try:
        client = _get_ssh_client(host)
        _, out, err = _ssh_exec(client, f'cd {service_dir} && docker-compose stop 2>&1 || docker compose stop 2>&1')
        deployment.status = 'stopped'
        deployment.deploy_log += f'\n[✓] 服务已停止\n{out}{err}'
        client.close()
    except Exception as exc:
        deployment.deploy_log += f'\n[✗] 停止失败: {str(exc)}'

    deployment.save(update_fields=['status', 'deploy_log'])
    return deployment


def start_service(deployment):
    """启动已停止的服务"""
    if deployment.deploy_mode == 'k8s':
        try:
            replicas = max(deployment.replicas or 1, 1)
            scaled = _scale_k8s_workloads(deployment, replicas)
            if not scaled:
                raise RuntimeError('未找到可启动的 K8s 工作负载')
            deployment.status = 'running'
            deployment.deploy_log += f'\n[✓] 已恢复副本数到 {replicas}: {", ".join(scaled)}'
        except Exception as exc:
            deployment.deploy_log += f'\n[✗] 启动失败: {str(exc)}'
        deployment.save(update_fields=['status', 'deploy_log'])
        return deployment

    host = deployment.host
    service_dir = deployment.deploy_dir

    try:
        client = _get_ssh_client(host)
        _, out, err = _ssh_exec(client, f'cd {service_dir} && docker-compose start 2>&1 || docker compose start 2>&1')
        deployment.status = 'running'
        deployment.deploy_log += f'\n[✓] 服务已启动\n{out}{err}'
        client.close()
    except Exception as exc:
        deployment.deploy_log += f'\n[✗] 启动失败: {str(exc)}'

    deployment.save(update_fields=['status', 'deploy_log'])
    return deployment


def _remove_k8s_resources(deployment):
    cluster = deployment.cluster
    if _is_demo(cluster):
        return ['Namespace scoped demo resources']

    client_module = _get_k8s_client(cluster)
    namespace = deployment.namespace or 'default'
    selector = _k8s_label_selector(deployment)
    deleted = []

    apps_v1 = client_module.AppsV1Api()
    batch_v1 = client_module.BatchV1Api()
    networking_v1 = client_module.NetworkingV1Api()
    core_v1 = client_module.CoreV1Api()

    apps_v1.delete_collection_namespaced_deployment(namespace, label_selector=selector)
    deleted.append('Deployment')
    apps_v1.delete_collection_namespaced_stateful_set(namespace, label_selector=selector)
    deleted.append('StatefulSet')
    batch_v1.delete_collection_namespaced_job(namespace, label_selector=selector)
    deleted.append('Job')
    batch_v1.delete_collection_namespaced_cron_job(namespace, label_selector=selector)
    deleted.append('CronJob')
    networking_v1.delete_collection_namespaced_ingress(namespace, label_selector=selector)
    deleted.append('Ingress')
    core_v1.delete_collection_namespaced_service(namespace, label_selector=selector)
    deleted.append('Service')
    core_v1.delete_collection_namespaced_config_map(namespace, label_selector=selector)
    deleted.append('ConfigMap')
    core_v1.delete_collection_namespaced_secret(namespace, label_selector=selector)
    deleted.append('Secret')
    core_v1.delete_collection_namespaced_persistent_volume_claim(namespace, label_selector=selector)
    deleted.append('PVC')

    return deleted


def remove_service(deployment):
    """卸载服务"""
    if deployment.deploy_mode == 'k8s':
        try:
            deleted = _remove_k8s_resources(deployment)
            deployment.deploy_log += f'\n[✓] 已删除 K8s 资源: {", ".join(deleted)}'
        except Exception as exc:
            deployment.deploy_log += f'\n[✗] 卸载失败: {str(exc)}'
            deployment.save(update_fields=['deploy_log'])
            return deployment

        deployment.save(update_fields=['deploy_log'])
        deployment.delete()
        return None

    host = deployment.host
    service_dir = deployment.deploy_dir

    try:
        client = _get_ssh_client(host)
        _, out, err = _ssh_exec(client, f'cd {service_dir} && docker-compose down -v 2>&1 || docker compose down -v 2>&1')
        _ssh_exec(client, f'rm -rf {service_dir}')
        deployment.deploy_log += f'\n[✓] 服务已卸载并清理\n{out}{err}'
        client.close()
    except Exception as exc:
        deployment.deploy_log += f'\n[✗] 卸载失败: {str(exc)}'
        deployment.save(update_fields=['deploy_log'])
        return deployment

    deployment.save(update_fields=['deploy_log'])
    deployment.delete()
    return None


def get_service_logs(deployment, tail=100):
    """获取服务日志"""
    if deployment.deploy_mode == 'k8s':
        cluster = deployment.cluster
        namespace = deployment.namespace or 'default'

        if _is_demo(cluster):
            return (
                f'[{namespace}/{deployment.release_name}] demo-pod-0 started\n'
                f'[{namespace}/{deployment.release_name}] service is running in demo cluster {cluster.name}'
            )

        try:
            client_module = _get_k8s_client(cluster)
            v1 = client_module.CoreV1Api()
            pods = v1.list_namespaced_pod(namespace, label_selector=_k8s_label_selector(deployment)).items
            pod = _select_k8s_pod(pods)
            if pod is None:
                return '未找到关联 Pod，暂无法获取日志'
            return v1.read_namespaced_pod_log(pod.metadata.name, namespace, tail_lines=tail)
        except Exception as exc:
            return f'获取日志失败: {str(exc)}'

    host = deployment.host
    service_dir = deployment.deploy_dir

    try:
        client = _get_ssh_client(host)
        _, out, err = _ssh_exec(
            client,
            f'cd {service_dir} && docker-compose logs --tail={tail} 2>&1 || docker compose logs --tail={tail} 2>&1',
        )
        client.close()
        return out or err
    except Exception as exc:
        return f'获取日志失败: {str(exc)}'
