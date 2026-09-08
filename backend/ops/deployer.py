import json
import logging
import re
import threading

import paramiko
import yaml
from django.core.cache import cache
from django.db import close_old_connections, transaction
from django.utils import timezone
from django.utils.text import slugify
from kubernetes import utils as k8s_utils
from kubernetes.client.exceptions import ApiException

from cmdb.models import CIType, CIRelation, ConfigItem
from eventwall.models import EventRecord
from eventwall.services import build_resource, record_event
from ops.k8s_views import _get_k8s_client, _is_demo

from .models import Deployment

logger = logging.getLogger(__name__)

DEPLOY_BASE = '/opt/sxdevops/apps'
SERVICE_STATUS_CACHE_TTL = 8
SERVICE_STATUS_STALE_CACHE_TTL = 300
CMDB_ENV_MAP = {
    'production': 'prod',
    'staging': 'test',
    'testing': 'test',
    'development': 'dev',
    'prod': 'prod',
    'test': 'test',
    'dev': 'dev',
}


def _app_slug(value):
    return slugify(value) or re.sub(r'[^a-z0-9]+', '-', (value or '').lower()).strip('-') or 'app'


def _default_release_name(deployment):
    return f'{_app_slug(deployment.app_name)}-{deployment.environment}'


def _service_status_cache_key(deployment):
    return (
        f'ops:deployment:status:{deployment.id}:'
        f'{deployment.status}:{deployment.approval_status}:{int(bool(deployment.is_current))}:'
        f'{deployment.batch_current or 0}:{deployment.batch_total or 0}'
    )


def _cmdb_environment(value):
    return CMDB_ENV_MAP.get(value, value or 'test')


def _cmdb_ci_name(deployment):
    return f'{deployment.app_name}-{_cmdb_environment(deployment.environment)}'


def _docker_target(deployment):
    return deployment.docker_host or deployment.host


def _docker_target_name(target):
    return getattr(target, 'name', '') or getattr(target, 'hostname', '') or '-'


def _docker_target_cmdb_status(target):
    status = getattr(target, 'status', '')
    if status in ('connected', 'online'):
        return 'active'
    return 'offline'


def _is_demo_docker(deployment):
    docker_target = _docker_target(deployment)
    if not docker_target:
        return False
    description = str(getattr(docker_target, 'description', '') or '')
    image = str(getattr(deployment, 'image', '') or '')
    return '婕旂ず' in description or image.startswith('registry.demo.local/')


def _cmdb_status_for_deployment(deployment, override=None):
    if override:
        return override
    if deployment.status == 'running':
        return 'active'
    if deployment.status == 'stopped':
        return 'idle'
    if deployment.status == 'removed':
        return 'offline'
    return 'active'


def _ensure_cmdb_app_ci_type():
    ci_type, _ = CIType.objects.get_or_create(
        name='应用服务',
        defaults={
            'icon': 'Promotion',
            'color': '#3b82f6',
            'description': '\u7531\u5e94\u7528\u53d1\u5e03\u6a21\u5757\u81ea\u52a8\u540c\u6b65\u7684\u4e1a\u52a1\u5e94\u7528\u914d\u7f6e\u9879',
        },
    )
    changed = False
    if not ci_type.icon:
        ci_type.icon = 'Promotion'
        changed = True
    if not ci_type.color:
        ci_type.color = '#3b82f6'
        changed = True
    if not ci_type.description:
        ci_type.description = '\u7531\u5e94\u7528\u53d1\u5e03\u6a21\u5757\u81ea\u52a8\u540c\u6b65\u7684\u4e1a\u52a1\u5e94\u7528\u914d\u7f6e\u9879'
        changed = True
    if changed:
        ci_type.save(update_fields=['icon', 'color', 'description'])
    return ci_type


def _ensure_cmdb_ci_type(name, icon, color, description):
    ci_type, _ = CIType.objects.get_or_create(
        name=name,
        defaults={
            'icon': icon,
            'color': color,
            'description': description,
        },
    )
    changed = False
    if not ci_type.icon:
        ci_type.icon = icon
        changed = True
    if not ci_type.color:
        ci_type.color = color
        changed = True
    if not ci_type.description:
        ci_type.description = description
        changed = True
    if changed:
        ci_type.save(update_fields=['icon', 'color', 'description'])
    return ci_type


def _ensure_target_cmdb_item(deployment):
    environment = _cmdb_environment(deployment.environment)
    docker_target = _docker_target(deployment)
    if deployment.deploy_mode == 'docker_compose' and docker_target:
        ci_type = _ensure_cmdb_ci_type('Docker环境', 'Box', '#10b981', '由应用发布模块自动同步的 Docker 发布目标')
        ci, _ = ConfigItem.objects.get_or_create(
            ci_type=ci_type,
            name=_docker_target_name(docker_target),
            business_line=deployment.business_line,
            environment=environment,
            defaults={
                'admin_user': docker_target.ssh_user or '',
                'status': _docker_target_cmdb_status(docker_target),
                'attributes': {},
            },
        )
        ci.admin_user = docker_target.ssh_user or ci.admin_user
        ci.status = _docker_target_cmdb_status(docker_target)
        ci.attributes = {
            **(ci.attributes or {}),
            'source': 'app_release_target',
            'target_kind': 'docker_environment',
            'environment_name': _docker_target_name(docker_target),
            'ip_address': docker_target.ip_address,
            'ssh_port': docker_target.ssh_port,
        }
        ci.save()
        return ci

    if deployment.deploy_mode == 'k8s' and deployment.cluster_id:
        ci_type = _ensure_cmdb_ci_type('K8s 集群', 'Connection', '#0ea5e9', '由应用发布模块自动同步的集群发布目标')
        ci, _ = ConfigItem.objects.get_or_create(
            ci_type=ci_type,
            name=deployment.cluster.name,
            business_line=deployment.business_line,
            environment=environment,
            defaults={
                'admin_user': '',
                'status': 'active',
                'attributes': {},
            },
        )
        ci.status = 'active'
        ci.attributes = {
            **(ci.attributes or {}),
            'source': 'app_release_target',
            'target_kind': 'cluster',
            'cluster_name': deployment.cluster.name,
            'api_server': deployment.cluster.api_server,
            'namespace': deployment.namespace or 'default',
        }
        ci.save()
        return ci

    return None


def sync_deployment_to_cmdb(deployment, override_status=None):
    if not deployment.business_line:
        return None

    ci_type = _ensure_cmdb_app_ci_type()
    environment = _cmdb_environment(deployment.environment)
    ci_name = _cmdb_ci_name(deployment)
    ci, _ = ConfigItem.objects.get_or_create(
        ci_type=ci_type,
        name=ci_name,
        business_line=deployment.business_line,
        environment=environment,
        defaults={
            'admin_user': deployment.deployer or deployment.submitter or '',
            'status': _cmdb_status_for_deployment(deployment, override_status),
            'attributes': {},
        },
    )
    ci.admin_user = deployment.deployer or deployment.submitter or ci.admin_user
    ci.status = _cmdb_status_for_deployment(deployment, override_status)
    ci.attributes = {
        **(ci.attributes or {}),
        'source': 'app_release',
        'deployment_id': deployment.id,
        'app_name': deployment.app_name,
        'version': deployment.version,
        'image': deployment.image,
        'deploy_mode': deployment.deploy_mode,
        'deploy_target': deployment.target_display,
        'release_name': deployment.release_name_display,
        'namespace': deployment.namespace or '',
        'replicas': deployment.replicas,
        'container_port': deployment.container_port,
        'service_port': deployment.service_port,
        'release_strategy': deployment.release_strategy,
        'canary_percent': deployment.canary_percent,
        'batch_total': deployment.batch_total,
        'batch_current': deployment.batch_current,
        'deploy_dir': deployment.deploy_dir,
        'submitter': deployment.submitter,
        'deployer': deployment.deployer,
        'cluster_name': deployment.cluster.name if deployment.cluster_id else '',
        'docker_environment_name': deployment.docker_host.name if deployment.docker_host_id else '',
        'docker_environment_ip': deployment.docker_host.ip_address if deployment.docker_host_id else '',
        'host_name': deployment.host.hostname if deployment.host_id else '',
        'host_ip': deployment.host.ip_address if deployment.host_id else '',
        'ip_address': (
            deployment.host.ip_address if deployment.host_id else
            deployment.docker_host.ip_address if deployment.docker_host_id else
            (ci.attributes or {}).get('ip_address', '')
        ),
    }
    ci.save()
    target_ci = _ensure_target_cmdb_item(deployment)
    if target_ci:
        CIRelation.objects.get_or_create(
            source=ci,
            target=target_ci,
            relation_type='runs_on',
            defaults={'description': '搴旂敤鍙戝竷鑷姩鍏宠仈鍙戝竷鐩爣'},
        )
    return ci


def sync_current_deployments_to_cmdb():
    for deployment in (
        Deployment.objects.select_related('host', 'docker_host', 'cluster')
        .filter(is_current=True, approval_status='approved', status__in=['running', 'stopped', 'removed'])
    ):
        try:
            sync_deployment_to_cmdb(deployment)
        except Exception:
            logger.exception('sync_current_deployments_to_cmdb error for deployment %s', deployment.id)


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


def _build_compose_payload(deployment):
    env_vars = deployment.env_config or {}
    service = {
        'image': deployment.image,
        'restart': 'always',
    }
    if env_vars:
        service['environment'] = env_vars
    if deployment.container_port and deployment.service_port:
        service['ports'] = [f'{deployment.service_port}:{deployment.container_port}']
    compose = {
        'services': {
            deployment.release_name_display: service,
        }
    }
    return yaml.safe_dump(compose, sort_keys=False, allow_unicode=True)


def _build_k8s_documents(deployment):
    release_name = deployment.release_name_display
    namespace = deployment.namespace or 'default'
    labels = {
        'app.kubernetes.io/managed-by': 'sxdevops',
        'app.kubernetes.io/name': _app_slug(deployment.app_name),
        'app.kubernetes.io/instance': release_name,
        'sxdevops/environment': deployment.environment,
    }
    env_items = [{'name': str(key).upper(), 'value': str(value)} for key, value in (deployment.env_config or {}).items()]
    container = {
        'name': _app_slug(deployment.app_name),
        'image': deployment.image,
        'env': env_items,
    }
    if deployment.container_port:
        container['ports'] = [{'containerPort': deployment.container_port}]

    documents = [{
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {
            'name': release_name,
            'namespace': namespace,
            'labels': labels,
        },
        'spec': {
            'replicas': deployment.replicas or 1,
            'selector': {'matchLabels': labels},
            'template': {
                'metadata': {'labels': labels},
                'spec': {'containers': [container]},
            },
        },
    }]
    if deployment.service_port:
        documents.append({
            'apiVersion': 'v1',
            'kind': 'Service',
            'metadata': {
                'name': release_name,
                'namespace': namespace,
                'labels': labels,
            },
            'spec': {
                'selector': labels,
                'ports': [{
                    'port': deployment.service_port,
                    'targetPort': deployment.container_port or deployment.service_port,
                }],
            },
        })
    return documents


def _mark_current_release(deployment):
    with transaction.atomic():
        deployment.same_target_queryset().exclude(pk=deployment.pk).filter(is_current=True).update(is_current=False)
        deployment.is_current = True
        deployment.save(update_fields=['is_current'])


def _deployment_event_metadata(deployment, **extra):
    metadata = {
        'event_category': 'application_release',
        'service': deployment.app_name,
        'service_name': deployment.app_name,
        'version': deployment.version,
        'release_version': deployment.version,
        'release_name': deployment.release_name,
        'action_type': deployment.action_type,
        'deploy_mode': deployment.deploy_mode,
        'release_strategy': deployment.release_strategy,
        'image': deployment.image,
        'namespace': deployment.namespace,
    }
    metadata.update({key: value for key, value in extra.items() if value not in (None, '')})
    return metadata


def _strategy_log_lines(deployment):
    if deployment.release_strategy == 'canary':
        return [f'[INFO] 发布策略: 灰度发布 {deployment.canary_percent}%']
    if deployment.release_strategy == 'batch':
        return [f'[INFO] 发布策略: 批次发布，共 {deployment.batch_total} 批，单批规模 {deployment.batch_size}']
    return ['[INFO] 发布策略: 标准发布']


def start_deployment_thread(deployment_id):
    thread = threading.Thread(target=deploy_service, args=(deployment_id,), daemon=True)
    thread.start()
    return thread


def _deploy_docker_compose(deployment, log_lines):
    docker_target = _docker_target(deployment)
    if not docker_target:
        raise RuntimeError('未配置 Docker 发布环境')
    release_name = deployment.release_name_display or _default_release_name(deployment)
    service_dir = f'{DEPLOY_BASE}/{release_name}'
    deployment.release_name = release_name
    deployment.deploy_dir = service_dir
    deployment.save(update_fields=['release_name', 'deploy_dir'])

    compose_content = _build_compose_payload(deployment)
    client = _get_ssh_client(docker_target)
    try:
        log_lines.append(f'[INFO] SSH 连接成功: {_docker_target_name(docker_target)} ({docker_target.ip_address})')
        _ssh_exec(client, f'mkdir -p {service_dir}')
        log_lines.append(f'[INFO] 创建目录: {service_dir}')
        sftp = client.open_sftp()
        with sftp.file(f'{service_dir}/docker-compose.yml', 'w') as file_obj:
            file_obj.write(compose_content)
        sftp.close()
        log_lines.append('[INFO] 已上传 docker-compose.yml')

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


def _ensure_k8s_namespace(client_module, namespace):
    namespace = namespace or 'default'
    core_v1 = client_module.CoreV1Api()
    try:
        core_v1.read_namespace(namespace)
        return False
    except ApiException as exc:
        if exc.status != 404:
            raise
    namespace_body = client_module.V1Namespace(
        metadata=client_module.V1ObjectMeta(name=namespace, labels={'app.kubernetes.io/managed-by': 'sxdevops'})
    )
    core_v1.create_namespace(namespace_body)
    return True


def _label_selector(deployment):
    return ','.join([
        f'app.kubernetes.io/name={_app_slug(deployment.app_name)}',
        f'app.kubernetes.io/instance={deployment.release_name_display}',
        f'sxdevops/environment={deployment.environment}',
    ])


def _deploy_k8s(deployment, log_lines):
    namespace = deployment.namespace or 'default'
    release_name = deployment.release_name_display or _default_release_name(deployment)
    deployment.release_name = release_name
    deployment.deploy_dir = f'k8s://{deployment.cluster.name}/{namespace}/{release_name}'
    deployment.save(update_fields=['release_name', 'deploy_dir'])

    if _is_demo(deployment.cluster):
        log_lines.extend([
            f'[INFO] 已连接 Demo K8s 集群: {deployment.cluster.name}',
            f'[INFO] 命名空间: {namespace}',
            f'[INFO] 发布名称: {release_name}',
            '[INFO] Demo 模式已模拟创建应用工作负载',
        ])
        return

    client_module = _get_k8s_client(deployment.cluster)
    created = _ensure_k8s_namespace(client_module, namespace)
    log_lines.append(f'[INFO] {"created" if created else "reused"} namespace: {namespace}')
    api_client = client_module.ApiClient()
    for document in _build_k8s_documents(deployment):
        k8s_utils.create_from_dict(api_client, document, namespace=namespace, verbose=False)
        log_lines.append(f'[INFO] 已创建 {document["kind"]}/{document["metadata"]["name"]}')


def deploy_service(deployment_id):
    close_old_connections()
    try:
        deployment = Deployment.objects.select_related('host', 'docker_host', 'cluster').get(pk=deployment_id)
    except Deployment.DoesNotExist:
        logger.error('Deployment %s not found', deployment_id)
        return

    deployment.status = 'deploying'
    deployment.deploy_log = ''
    deployment.execution_count = (deployment.execution_count or 0) + 1
    deployment.executed_at = timezone.now()
    deployment.finished_at = None
    deployment.is_current = False
    deployment.save(update_fields=['status', 'deploy_log', 'execution_count', 'executed_at', 'finished_at', 'is_current'])
    log_lines = [
        f'[INFO] 发布类型: {deployment.get_action_type_display()}',
        f'[INFO] 发布模式: {deployment.get_deploy_mode_display()}',
        f'[INFO] 应用: {deployment.app_name}',
        f'[INFO] 版本: {deployment.version}',
    ]
    log_lines.extend(_strategy_log_lines(deployment))
    if deployment.change_summary:
        log_lines.append(f'[INFO] 变更说明: {deployment.change_summary}')

    try:
        if deployment.deploy_mode == 'k8s':
            _deploy_k8s(deployment, log_lines)
        else:
            _deploy_docker_compose(deployment, log_lines)
        deployment.status = 'running'
        deployment.finished_at = timezone.now()
        if deployment.release_strategy == 'batch':
            deployment.batch_current = max(deployment.batch_current or 0, 1)
            log_lines.append(f'[INFO] 批次进度: 1/{deployment.batch_total}')
        log_lines.append('[SUCCESS] 发布成功')
        _mark_current_release(deployment)
        try:
            sync_deployment_to_cmdb(deployment, override_status='active')
        except Exception:
            logger.exception('sync_deployment_to_cmdb error after deploy success')
        record_event(
            module='ops',
            category='execution',
            action='deploy_finish',
            title='发布执行成功',
            summary=f'发布单 {deployment.app_name} 执行成功',
            result=EventRecord.RESULT_SUCCESS,
            source_type=EventRecord.SOURCE_ASYNC,
            actor_type=EventRecord.ACTOR_SYSTEM,
            actor_username=deployment.deployer or deployment.submitter or 'system',
            actor_display=deployment.deployer or deployment.submitter or 'system',
            resource_type='deployment',
            resource_id=deployment.id,
            resource_name=deployment.app_name,
            business_line=deployment.business_line,
            environment=deployment.environment,
            application=deployment.app_name,
            correlation_id=f'deployment:{deployment.id}',
            metadata=_deployment_event_metadata(deployment, execution_count=deployment.execution_count),
        )
    except Exception as exc:
        logger.exception('deploy_service error')
        deployment.status = 'failed'
        deployment.finished_at = timezone.now()
        log_lines.append(f'[ERROR] 发布失败: {str(exc)}')
        record_event(
            module='ops',
            category='execution',
            action='deploy_finish',
            title='发布执行失败',
            summary=f'发布单 {deployment.app_name} 执行失败',
            result=EventRecord.RESULT_FAILED,
            severity=EventRecord.SEVERITY_WARNING,
            source_type=EventRecord.SOURCE_ASYNC,
            actor_type=EventRecord.ACTOR_SYSTEM,
            actor_username=deployment.deployer or deployment.submitter or 'system',
            actor_display=deployment.deployer or deployment.submitter or 'system',
            resource_type='deployment',
            resource_id=deployment.id,
            resource_name=deployment.app_name,
            business_line=deployment.business_line,
            environment=deployment.environment,
            application=deployment.app_name,
            correlation_id=f'deployment:{deployment.id}',
            metadata=_deployment_event_metadata(deployment, error=str(exc)),
        )

    deployment.deploy_log = '\n'.join(log_lines)
    deployment.save(update_fields=['status', 'finished_at', 'deploy_log', 'batch_current'])
    close_old_connections()
    return deployment


def _scale_k8s_workloads(deployment, replicas):
    if _is_demo(deployment.cluster):
        return [f'Deployment/{deployment.release_name_display}']
    client_module = _get_k8s_client(deployment.cluster)
    apps_v1 = client_module.AppsV1Api()
    namespace = deployment.namespace or 'default'
    selector = _label_selector(deployment)
    body = {'spec': {'replicas': replicas}}
    scaled = []
    for item in apps_v1.list_namespaced_deployment(namespace, label_selector=selector).items:
        apps_v1.patch_namespaced_deployment_scale(item.metadata.name, namespace, body)
        scaled.append(f'Deployment/{item.metadata.name}')
    for item in apps_v1.list_namespaced_stateful_set(namespace, label_selector=selector).items:
        apps_v1.patch_namespaced_stateful_set_scale(item.metadata.name, namespace, body)
        scaled.append(f'StatefulSet/{item.metadata.name}')
    return scaled


def stop_service(deployment):
    if not deployment.is_current:
        deployment.deploy_log += '\n[WARN] 只能停止当前生效版本'
        deployment.save(update_fields=['deploy_log'])
        return deployment
    if deployment.deploy_mode == 'k8s':
        try:
            scaled = _scale_k8s_workloads(deployment, 0)
            deployment.status = 'stopped'
            deployment.deploy_log += f'\n[SUCCESS] 已缩容到 0 副本: {", ".join(scaled)}'
        except Exception as exc:
            deployment.deploy_log += f'\n[ERROR] 停止失败: {str(exc)}'
        deployment.finished_at = timezone.now()
        deployment.save(update_fields=['status', 'deploy_log', 'finished_at'])
        try:
            sync_deployment_to_cmdb(deployment, override_status='idle')
        except Exception:
            logger.exception('sync_deployment_to_cmdb error after stop')
        return deployment

    if not deployment.deploy_dir:
        deployment.deploy_log += '\n[ERROR] 无发布目录，无法停止'
        deployment.save(update_fields=['deploy_log'])
        return deployment
    docker_target = _docker_target(deployment)
    client = _get_ssh_client(docker_target)
    try:
        _, out, err = _ssh_exec(client, f'cd {deployment.deploy_dir} && docker-compose stop 2>&1 || docker compose stop 2>&1')
        deployment.status = 'stopped'
        deployment.deploy_log += f'\n[SUCCESS] 应用已停止\n{out}{err}'
    except Exception as exc:
        deployment.deploy_log += f'\n[ERROR] 停止失败: {str(exc)}'
    finally:
        client.close()
    deployment.finished_at = timezone.now()
    deployment.save(update_fields=['status', 'deploy_log', 'finished_at'])
    try:
        sync_deployment_to_cmdb(deployment, override_status='idle')
    except Exception:
        logger.exception('sync_deployment_to_cmdb error after stop')
    return deployment


def start_service(deployment):
    if not deployment.is_current:
        deployment.deploy_log += '\n[WARN] 只能启动当前生效版本'
        deployment.save(update_fields=['deploy_log'])
        return deployment
    if deployment.deploy_mode == 'k8s':
        try:
            scaled = _scale_k8s_workloads(deployment, max(deployment.replicas or 1, 1))
            deployment.status = 'running'
            deployment.deploy_log += f'\n[SUCCESS] 已恢复副本数: {", ".join(scaled)}'
        except Exception as exc:
            deployment.deploy_log += f'\n[ERROR] 启动失败: {str(exc)}'
        deployment.finished_at = timezone.now()
        deployment.save(update_fields=['status', 'deploy_log', 'finished_at'])
        try:
            sync_deployment_to_cmdb(deployment, override_status='active')
        except Exception:
            logger.exception('sync_deployment_to_cmdb error after start')
        return deployment

    docker_target = _docker_target(deployment)
    client = _get_ssh_client(docker_target)
    try:
        _, out, err = _ssh_exec(client, f'cd {deployment.deploy_dir} && docker-compose start 2>&1 || docker compose start 2>&1')
        deployment.status = 'running'
        deployment.deploy_log += f'\n[SUCCESS] 应用已启动\n{out}{err}'
    except Exception as exc:
        deployment.deploy_log += f'\n[ERROR] 启动失败: {str(exc)}'
    finally:
        client.close()
    deployment.finished_at = timezone.now()
    deployment.save(update_fields=['status', 'deploy_log', 'finished_at'])
    try:
        sync_deployment_to_cmdb(deployment, override_status='active')
    except Exception:
        logger.exception('sync_deployment_to_cmdb error after start')
    return deployment


def _remove_k8s_resources(deployment):
    if _is_demo(deployment.cluster):
        return ['Namespace scoped demo resources']
    client_module = _get_k8s_client(deployment.cluster)
    namespace = deployment.namespace or 'default'
    selector = _label_selector(deployment)
    apps_v1 = client_module.AppsV1Api()
    core_v1 = client_module.CoreV1Api()
    deleted = []
    apps_v1.delete_collection_namespaced_deployment(namespace, label_selector=selector)
    deleted.append('Deployment')
    apps_v1.delete_collection_namespaced_stateful_set(namespace, label_selector=selector)
    deleted.append('StatefulSet')
    core_v1.delete_collection_namespaced_service(namespace, label_selector=selector)
    deleted.append('Service')
    return deleted


def remove_service(deployment):
    if not deployment.is_current:
        deployment.deploy_log += '\n[WARN] 只能下线当前生效版本'
        deployment.save(update_fields=['deploy_log'])
        return deployment
    if deployment.deploy_mode == 'k8s':
        try:
            deleted = _remove_k8s_resources(deployment)
            deployment.deploy_log += f'\n[SUCCESS] 已删除 K8s 资源: {", ".join(deleted)}'
            deployment.status = 'removed'
            deployment.is_current = False
        except Exception as exc:
            deployment.deploy_log += f'\n[ERROR] 下线失败: {str(exc)}'
        deployment.finished_at = timezone.now()
        deployment.save(update_fields=['status', 'is_current', 'deploy_log', 'finished_at'])
        try:
            sync_deployment_to_cmdb(deployment, override_status='offline')
        except Exception:
            logger.exception('sync_deployment_to_cmdb error after remove')
        return deployment

    docker_target = _docker_target(deployment)
    client = _get_ssh_client(docker_target)
    try:
        _, out, err = _ssh_exec(client, f'cd {deployment.deploy_dir} && docker-compose down -v 2>&1 || docker compose down -v 2>&1')
        _ssh_exec(client, f'rm -rf {deployment.deploy_dir}')
        deployment.deploy_log += f'\n[SUCCESS] 应用已下线\n{out}{err}'
        deployment.status = 'removed'
        deployment.is_current = False
    except Exception as exc:
        deployment.deploy_log += f'\n[ERROR] 下线失败: {str(exc)}'
    finally:
        client.close()
    deployment.finished_at = timezone.now()
    deployment.save(update_fields=['status', 'is_current', 'deploy_log', 'finished_at'])
    try:
        sync_deployment_to_cmdb(deployment, override_status='offline')
    except Exception:
        logger.exception('sync_deployment_to_cmdb error after remove')
    return deployment


def advance_batch(deployment, actor='', change_summary=''):
    if deployment.release_strategy != 'batch':
        raise ValueError('当前发布单不是批次发布')
    if deployment.approval_status != 'approved':
        raise ValueError('只有审批通过的发布单才能推进批次')
    if not deployment.is_current:
        raise ValueError('只能推进当前生效版本的批次')
    if deployment.status not in ('running', 'stopped'):
        raise ValueError('当前状态不支持推进批次')
    if (deployment.batch_current or 0) >= (deployment.batch_total or 1):
        raise ValueError('批次发布已经全部完成')

    deployment.batch_current = (deployment.batch_current or 0) + 1
    deployment.finished_at = timezone.now()
    message = f'\n[INFO] 批次推进: 第 {deployment.batch_current}/{deployment.batch_total} 批'
    if actor:
        message += f'，操作人 {actor}'
    if change_summary:
        message += f'，说明: {change_summary}'
    if deployment.batch_current >= deployment.batch_total:
        message += '\n[SUCCESS] 批次发布已完成'
    deployment.deploy_log = f'{deployment.deploy_log}{message}'.strip()
    deployment.save(update_fields=['batch_current', 'finished_at', 'deploy_log'])
    return deployment


def get_service_logs(deployment, tail=100):
    if not deployment.is_current:
        return '该发布已被后续版本接管，以下展示归档日志：\n\n' + (deployment.deploy_log or '暂无日志')
    if deployment.deploy_mode == 'k8s':
        if _is_demo(deployment.cluster):
            return f'[{deployment.namespace or "default"}/{deployment.release_name_display}] demo pod running'
        try:
            client_module = _get_k8s_client(deployment.cluster)
            core_v1 = client_module.CoreV1Api()
            pods = core_v1.list_namespaced_pod(deployment.namespace or 'default', label_selector=_label_selector(deployment)).items
            if not pods:
                return '未找到关联 Pod'
            pod = sorted(pods, key=lambda item: item.metadata.name)[0]
            return core_v1.read_namespaced_pod_log(pod.metadata.name, deployment.namespace or 'default', tail_lines=tail)
        except Exception as exc:
            return f'获取日志失败: {str(exc)}'

    if _is_demo_docker(deployment):
        return (
            f'[{deployment.release_name_display}] demo container running\n'
            f'image={deployment.image}\n'
            f'target={deployment.target_display}\n'
            f'batch={deployment.batch_current or 1}/{deployment.batch_total or 1}'
        )

    try:
        docker_target = _docker_target(deployment)
        client = _get_ssh_client(docker_target)
        _, out, err = _ssh_exec(client, f'cd {deployment.deploy_dir} && docker-compose logs --tail={tail} 2>&1 || docker compose logs --tail={tail} 2>&1')
        client.close()
        return out or err
    except Exception as exc:
        return f'获取日志失败: {str(exc)}'


def _docker_runtime_status(deployment):
    if not deployment.deploy_dir:
        return {'mode': 'docker_compose', 'summary': '尚未生成发布目录', 'items': []}
    if _is_demo_docker(deployment):
        current_batch = max(deployment.batch_current or 1, 1)
        batch_total = max(deployment.batch_total or 1, 1)
        return {
            'mode': 'docker_compose',
            'summary': f'Demo Docker 环境 {deployment.target_display} 运行正常',
            'items': [
                {
                    'kind': 'container',
                    'name': deployment.release_name_display,
                    'state': 'running',
                    'ports': (
                        f'{deployment.service_port}:{deployment.container_port}'
                        if deployment.service_port and deployment.container_port
                        else ''
                    ),
                },
                {
                    'kind': 'strategy',
                    'name': deployment.get_release_strategy_display(),
                    'state': deployment.strategy_summary,
                    'ports': f'批次 {current_batch}/{batch_total}' if deployment.release_strategy == 'batch' else '',
                },
            ],
        }
    docker_target = _docker_target(deployment)
    client = _get_ssh_client(docker_target)
    try:
        _, out, err = _ssh_exec(
            client,
            f'cd {deployment.deploy_dir} && (docker compose ps --all --format json 2>/dev/null || docker-compose ps 2>&1 || docker compose ps 2>&1)',
        )
    finally:
        client.close()
    raw = (out or err or '').strip()
    items = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            items.append({
                'kind': 'container',
                'name': payload.get('Name') or payload.get('Service') or '-',
                'state': payload.get('State') or payload.get('Status') or '-',
                'ports': payload.get('Publishers') or payload.get('Ports') or '',
            })
    if items:
        return {'mode': 'docker_compose', 'summary': f'容器数量: {len(items)}', 'items': items}
    return {'mode': 'docker_compose', 'summary': '已返回原始 docker compose 状态', 'items': [], 'raw': raw}


def _k8s_runtime_status(deployment):
    if _is_demo(deployment.cluster):
        return {
            'mode': 'k8s',
            'summary': f'Demo 集群 {deployment.cluster.name} 运行正常',
            'items': [
                {'kind': 'Deployment', 'name': deployment.release_name_display, 'state': 'Available', 'ready': '1/1'},
                {'kind': 'Pod', 'name': f'{deployment.release_name_display}-demo-0', 'state': 'Running', 'ready': '1/1'},
            ],
        }
    client_module = _get_k8s_client(deployment.cluster)
    apps_v1 = client_module.AppsV1Api()
    core_v1 = client_module.CoreV1Api()
    namespace = deployment.namespace or 'default'
    selector = _label_selector(deployment)
    items = []
    for item in apps_v1.list_namespaced_deployment(namespace, label_selector=selector).items:
        ready = getattr(item.status, 'ready_replicas', 0) or 0
        desired = getattr(item.spec, 'replicas', 0) or 0
        items.append({
            'kind': 'Deployment',
            'name': item.metadata.name,
            'state': 'Available' if ready == desired and desired else 'Progressing',
            'ready': f'{ready}/{desired}',
        })
    for item in core_v1.list_namespaced_pod(namespace, label_selector=selector).items:
        total = len(getattr(item.status, 'container_statuses', []) or [])
        ready = sum(1 for status in (getattr(item.status, 'container_statuses', []) or []) if getattr(status, 'ready', False))
        items.append({
            'kind': 'Pod',
            'name': item.metadata.name,
            'state': getattr(item.status, 'phase', '-') or '-',
            'ready': f'{ready}/{total or 1}',
        })
    return {'mode': 'k8s', 'summary': f'工作负载数量: {len(items)}', 'items': items}


def get_service_status(deployment):
    base = {
        'id': deployment.id,
        'status': deployment.status,
        'status_display': deployment.get_status_display(),
        'approval_status': deployment.approval_status,
        'approval_status_display': deployment.get_approval_status_display(),
        'release_strategy': deployment.release_strategy,
        'release_strategy_display': deployment.get_release_strategy_display(),
        'strategy_summary': deployment.strategy_summary,
        'canary_percent': deployment.canary_percent,
        'batch_total': deployment.batch_total,
        'batch_current': deployment.batch_current,
        'is_current': deployment.is_current,
    }
    if deployment.approval_status != 'approved':
        base.update({'summary': '尚未通过审批', 'items': [], 'message': '待审批或已驳回的发布单暂时没有运行状态'})
        return base
    if not deployment.is_current:
        base.update({'summary': '该发布已被后续版本接管', 'items': [], 'message': '请查看当前生效版本获取实时状态'})
        return base
    if deployment.status == 'removed':
        base.update({'summary': '当前版本已下线', 'items': []})
        return base
    cache_key = _service_status_cache_key(deployment)
    stale_key = f'{cache_key}:stale'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        runtime = _k8s_runtime_status(deployment) if deployment.deploy_mode == 'k8s' else _docker_runtime_status(deployment)
        base.update(runtime)
        cache.set(cache_key, base, SERVICE_STATUS_CACHE_TTL)
        cache.set(stale_key, base, SERVICE_STATUS_STALE_CACHE_TTL)
    except Exception as exc:
        logger.exception('get_service_status error')
        stale = cache.get(stale_key)
        if stale is not None:
            return {
                **stale,
                'degraded': True,
                'message': '运行状态采集超时，已返回最近一次缓存结果',
            }
        base.update({'summary': '状态采集失败', 'items': [], 'message': str(exc), 'degraded': True})
    return base
