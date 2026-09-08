import paramiko
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from django.utils.timezone import is_naive, make_aware
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from eventwall.mixins import EventWallModelViewSetMixin
from eventwall.models import EventRecord
from eventwall.services import build_resource, record_event
from rbac.permissions import RBACPermissionMixin

from .models import NginxCertificate, NginxDomain, NginxEnvironment, NginxRoute
from .nginx_conf_generator import generate_domain_conf
from .serializers import (
    NginxCertificateSerializer,
    NginxDomainSerializer,
    NginxEnvironmentSerializer,
    NginxRouteSerializer,
)


def _parse_certificate(cert_data):
    if not cert_data:
        return None, None
    try:
        cert = x509.load_pem_x509_certificate(cert_data.encode('utf-8'), default_backend())
        domain = None
        for attribute in cert.subject:
            if attribute.oid == x509.NameOID.COMMON_NAME:
                domain = attribute.value
                break

        if not domain:
            try:
                ext = cert.extensions.get_extension_for_oid(x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                sans = ext.value.get_values_for_type(x509.DNSName)
                if sans:
                    domain = sans[0]
            except Exception:
                pass

        expires_at = cert.not_valid_after
        if is_naive(expires_at):
            expires_at = make_aware(expires_at)
        return domain, expires_at
    except Exception:
        return None, None


def _get_ssh_client(env):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=env.ip_address,
        port=env.ssh_port or 22,
        username=env.ssh_user or 'root',
        password=env.ssh_password or None,
        timeout=10,
    )
    return client


def _ssh_exec(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    return stdout.read().decode('utf-8', errors='replace').strip()


def _deploy_domain_conf(domain_obj):
    env = domain_obj.environment
    nginx_path = env.nginx_path or '/etc/nginx'
    conf_dir = f'{nginx_path}/conf.d'
    disabled_dir = f'{conf_dir}/disabled'
    filename = domain_obj.conf_filename
    conf_content = generate_domain_conf(domain_obj)

    try:
        client = _get_ssh_client(env)
        _ssh_exec(client, f'mkdir -p {conf_dir} {disabled_dir}')

        sftp = client.open_sftp()
        if domain_obj.enabled:
            with sftp.file(f'{conf_dir}/{filename}', 'w') as file_obj:
                file_obj.write(conf_content)
            _ssh_exec(client, f'rm -f {disabled_dir}/{filename}')
        else:
            with sftp.file(f'{disabled_dir}/{filename}', 'w') as file_obj:
                file_obj.write(conf_content)
            _ssh_exec(client, f'rm -f {conf_dir}/{filename}')
        sftp.close()

        _ssh_exec(client, 'nginx -t && nginx -s reload')
        client.close()
        return True, '配置已下发并完成重载'
    except Exception as exc:
        return False, str(exc)


def _push_cert_to_env(cert, env):
    nginx_path = env.nginx_path or '/etc/nginx'
    ssl_dir = f'{nginx_path}/ssl'

    try:
        client = _get_ssh_client(env)
        _ssh_exec(client, f'mkdir -p {ssl_dir}')
        sftp = client.open_sftp()
        with sftp.file(f'{ssl_dir}/{cert.cert_filename}', 'w') as file_obj:
            file_obj.write(cert.cert_content)
        with sftp.file(f'{ssl_dir}/{cert.key_filename}', 'w') as file_obj:
            file_obj.write(cert.key_content)
        _ssh_exec(client, f'chmod 600 {ssl_dir}/{cert.key_filename}')
        sftp.close()
        client.close()
        return True, f'证书已推送到 {env.name} ({ssl_dir}/)'
    except Exception as exc:
        return False, str(exc)


def _remove_cert_from_env(cert, env):
    nginx_path = env.nginx_path or '/etc/nginx'
    ssl_dir = f'{nginx_path}/ssl'

    try:
        client = _get_ssh_client(env)
        _ssh_exec(client, f'rm -f {ssl_dir}/{cert.cert_filename} {ssl_dir}/{cert.key_filename}')
        client.close()
        return True, f'证书已从 {env.name} 删除'
    except Exception as exc:
        return False, str(exc)


class NginxEnvironmentViewSet(EventWallModelViewSetMixin, RBACPermissionMixin, viewsets.ModelViewSet):
    queryset = NginxEnvironment.objects.all()
    serializer_class = NginxEnvironmentSerializer
    search_fields = ['name', 'ip_address']
    event_module = 'ops'
    event_resource_type = 'nginx_environment'
    event_resource_label = 'Nginx 环境'
    event_resource_name_fields = ('name',)
    event_exclude_fields = ('ssh_password',)
    rbac_permissions = {
        'list': ['ops.nginx.view'],
        'retrieve': ['ops.nginx.view'],
        'create': ['ops.nginx.manage'],
        'update': ['ops.nginx.manage'],
        'partial_update': ['ops.nginx.manage'],
        'destroy': ['ops.nginx.manage'],
        'test_connection': ['ops.nginx.manage'],
    }

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        env = self.get_object()
        try:
            client = _get_ssh_client(env)
            stdin, stdout, stderr = client.exec_command('nginx -v', timeout=5)
            err_output = stderr.read().decode('utf-8', errors='replace').strip()
            out_output = stdout.read().decode('utf-8', errors='replace').strip()
            output = err_output if err_output else out_output
            client.close()

            success = 'nginx version' in output.lower()
            env.status = 'connected' if success else 'error'
            env.save(update_fields=['status'])
            record_event(
                request=request,
                module='ops',
                category='execution',
                action='test_connection',
                title='测试 Nginx 环境连通性',
                summary=f'Nginx 环境 {env.name} 连通性测试{"成功" if success else "失败"}',
                result=EventRecord.RESULT_SUCCESS if success else EventRecord.RESULT_FAILED,
                severity=EventRecord.SEVERITY_INFO if success else EventRecord.SEVERITY_WARNING,
                resource_type='nginx_environment',
                resource_id=env.id,
                resource_name=env.name,
                correlation_id=f'nginx-env:{env.id}',
                metadata={'ip_address': env.ip_address, 'output': output},
            )
            if success:
                return Response({'success': True, 'message': f'连接成功: {output}'})
            return Response({'success': False, 'message': f'已连接，但未识别到 Nginx: {output}'})
        except Exception as exc:
            env.status = 'disconnected'
            env.save(update_fields=['status'])
            record_event(
                request=request,
                module='ops',
                category='execution',
                action='test_connection',
                title='测试 Nginx 环境连通性',
                summary=f'Nginx 环境 {env.name} 连通性测试失败',
                result=EventRecord.RESULT_FAILED,
                severity=EventRecord.SEVERITY_WARNING,
                resource_type='nginx_environment',
                resource_id=env.id,
                resource_name=env.name,
                correlation_id=f'nginx-env:{env.id}',
                metadata={'ip_address': env.ip_address, 'error': str(exc)},
            )
            return Response({'success': False, 'message': f'连接失败: {str(exc)}'})


class NginxCertificateViewSet(EventWallModelViewSetMixin, RBACPermissionMixin, viewsets.ModelViewSet):
    queryset = NginxCertificate.objects.prefetch_related('environments').all()
    serializer_class = NginxCertificateSerializer
    search_fields = ['domain']
    event_module = 'ops'
    event_resource_type = 'nginx_certificate'
    event_resource_label = 'Nginx 证书'
    event_resource_name_fields = ('domain',)
    event_exclude_fields = ('cert_content', 'key_content')
    rbac_permissions = {
        'list': ['ops.nginx.view'],
        'retrieve': ['ops.nginx.view'],
        'create': ['ops.nginx.manage'],
        'update': ['ops.nginx.manage'],
        'partial_update': ['ops.nginx.manage'],
        'destroy': ['ops.nginx.manage'],
        'link_env': ['ops.nginx.manage'],
        'unlink_env': ['ops.nginx.manage'],
        'push_all': ['ops.nginx.manage'],
    }

    def perform_create(self, serializer):
        cert_content = serializer.validated_data.get('cert_content', '')
        domain, expires_at = _parse_certificate(cert_content)
        if not domain:
            raise ValidationError({'cert_content': '无效的证书内容，无法提取域名信息。'})
        serializer.save(domain=domain, expires_at=expires_at)

    def perform_update(self, serializer):
        cert_content = serializer.validated_data.get('cert_content', '')
        if cert_content:
            domain, expires_at = _parse_certificate(cert_content)
            if not domain:
                raise ValidationError({'cert_content': '无效的证书内容，无法提取域名信息。'})
            serializer.save(domain=domain, expires_at=expires_at)
        else:
            serializer.save()

    @action(detail=True, methods=['post'])
    def link_env(self, request, pk=None):
        cert = self.get_object()
        env_id = request.data.get('environment_id')
        if not env_id:
            return Response({'success': False, 'message': '请提供 environment_id'})

        try:
            env = NginxEnvironment.objects.get(id=env_id)
        except NginxEnvironment.DoesNotExist:
            return Response({'success': False, 'message': '环境不存在'})

        if not cert.cert_content or not cert.key_content:
            return Response({'success': False, 'message': '证书内容为空，无法推送'})

        cert.environments.add(env)
        ok, msg = _push_cert_to_env(cert, env)
        record_event(
            request=request,
            module='ops',
            category='execution',
            action='link_env',
            title='关联 Nginx 证书环境',
            summary=f'证书 {cert.domain} 已关联环境 {env.name}',
            result=EventRecord.RESULT_SUCCESS if ok else EventRecord.RESULT_FAILED,
            severity=EventRecord.SEVERITY_WARNING if not ok else EventRecord.SEVERITY_INFO,
            resource_type='nginx_certificate',
            resource_id=cert.id,
            resource_name=cert.domain,
            correlation_id=f'nginx-cert:{cert.id}',
            related_resources=[build_resource('ops', 'nginx_environment', env.id, env.name)],
            metadata={'message': msg},
        )
        return Response({'success': ok, 'message': msg})

    @action(detail=True, methods=['post'])
    def unlink_env(self, request, pk=None):
        cert = self.get_object()
        env_id = request.data.get('environment_id')
        if not env_id:
            return Response({'success': False, 'message': '请提供 environment_id'})

        try:
            env = NginxEnvironment.objects.get(id=env_id)
        except NginxEnvironment.DoesNotExist:
            return Response({'success': False, 'message': '环境不存在'})

        cert.environments.remove(env)
        ok, msg = _remove_cert_from_env(cert, env)
        record_event(
            request=request,
            module='ops',
            category='execution',
            action='unlink_env',
            title='解绑 Nginx 证书环境',
            summary=f'证书 {cert.domain} 已从环境 {env.name} 解绑',
            result=EventRecord.RESULT_SUCCESS if ok else EventRecord.RESULT_FAILED,
            severity=EventRecord.SEVERITY_WARNING,
            resource_type='nginx_certificate',
            resource_id=cert.id,
            resource_name=cert.domain,
            correlation_id=f'nginx-cert:{cert.id}',
            related_resources=[build_resource('ops', 'nginx_environment', env.id, env.name)],
            metadata={'message': msg},
        )
        return Response({'success': ok, 'message': msg})

    @action(detail=True, methods=['post'])
    def push_all(self, request, pk=None):
        cert = self.get_object()
        if not cert.cert_content or not cert.key_content:
            return Response({'success': False, 'message': '证书内容为空'})

        environments = list(cert.environments.all())
        results = []
        for env in environments:
            ok, msg = _push_cert_to_env(cert, env)
            results.append({'env': env.name, 'success': ok, 'message': msg})
        record_event(
            request=request,
            module='ops',
            category='execution',
            action='push_all',
            title='批量推送 Nginx 证书',
            summary=f'证书 {cert.domain} 已向 {len(results)} 个环境执行推送',
            result=EventRecord.RESULT_SUCCESS if all(item['success'] for item in results) else EventRecord.RESULT_PARTIAL,
            severity=EventRecord.SEVERITY_WARNING if any(not item['success'] for item in results) else EventRecord.SEVERITY_INFO,
            resource_type='nginx_certificate',
            resource_id=cert.id,
            resource_name=cert.domain,
            correlation_id=f'nginx-cert:{cert.id}',
            related_resources=[
                build_resource('ops', 'nginx_environment', env.id, env.name)
                for env in environments
            ],
            metadata={'results': results},
        )
        return Response({'success': True, 'results': results})


class NginxDomainViewSet(EventWallModelViewSetMixin, RBACPermissionMixin, viewsets.ModelViewSet):
    queryset = NginxDomain.objects.select_related('environment', 'certificate').all()
    serializer_class = NginxDomainSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['domain']
    filterset_fields = ['environment']
    event_module = 'ops'
    event_resource_type = 'nginx_domain'
    event_resource_label = 'Nginx 域名'
    event_resource_name_fields = ('domain',)
    rbac_permissions = {
        'list': ['ops.nginx.view'],
        'retrieve': ['ops.nginx.view'],
        'create': ['ops.nginx.manage'],
        'update': ['ops.nginx.manage'],
        'partial_update': ['ops.nginx.manage'],
        'destroy': ['ops.nginx.manage'],
        'deploy_conf': ['ops.nginx.manage'],
        'preview_conf': ['ops.nginx.view'],
    }

    @action(detail=True, methods=['post'])
    def deploy_conf(self, request, pk=None):
        domain = self.get_object()
        ok, msg = _deploy_domain_conf(domain)
        related_resources = []
        if domain.environment_id:
            related_resources.append(build_resource('ops', 'nginx_environment', domain.environment_id, domain.environment.name))
        if domain.certificate_id:
            related_resources.append(build_resource('ops', 'nginx_certificate', domain.certificate_id, domain.certificate.domain))
        record_event(
            request=request,
            module='ops',
            category='execution',
            action='deploy_conf',
            title='下发 Nginx 域名配置',
            summary=f'域名 {domain.domain} 已执行配置下发',
            result=EventRecord.RESULT_SUCCESS if ok else EventRecord.RESULT_FAILED,
            severity=EventRecord.SEVERITY_WARNING if not ok else EventRecord.SEVERITY_INFO,
            resource_type='nginx_domain',
            resource_id=domain.id,
            resource_name=domain.domain,
            correlation_id=f'nginx-domain:{domain.id}',
            related_resources=related_resources,
            metadata={'message': msg},
        )
        return Response({'success': ok, 'message': msg})

    @action(detail=True, methods=['get'])
    def preview_conf(self, request, pk=None):
        domain = self.get_object()
        conf = generate_domain_conf(domain)
        return Response({'conf': conf, 'filename': domain.conf_filename})


class NginxRouteViewSet(EventWallModelViewSetMixin, RBACPermissionMixin, viewsets.ModelViewSet):
    queryset = NginxRoute.objects.select_related('nginx_domain', 'nginx_domain__environment').all()
    serializer_class = NginxRouteSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['location', 'upstream_servers']
    filterset_fields = ['nginx_domain']
    event_module = 'ops'
    event_resource_type = 'nginx_route'
    event_resource_label = 'Nginx 路由'
    event_resource_name_fields = ('location',)
    rbac_permissions = {
        'list': ['ops.nginx.view'],
        'retrieve': ['ops.nginx.view'],
        'create': ['ops.nginx.manage'],
        'update': ['ops.nginx.manage'],
        'partial_update': ['ops.nginx.manage'],
        'destroy': ['ops.nginx.manage'],
    }
