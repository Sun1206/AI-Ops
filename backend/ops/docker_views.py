"""
Docker environment APIs.

- DockerHostViewSet: Docker host CRUD and connection testing
- Container/Image APIs: SSH to real hosts, or serve cached demo data for seeded demo hosts
"""
import hashlib
import json
import logging
import shlex

import paramiko
from django.core.cache import cache
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from rbac.permissions import RBACPermissionMixin, build_rbac_permission
from rbac.services import DEMO_ACCOUNT_MUTATION_MESSAGE, is_demo_account

from .models import DockerHost
from .serializers import DockerHostSerializer

logger = logging.getLogger(__name__)

DOCKER_LOG_TAIL_DEFAULT = 200
DOCKER_LOG_TAIL_MAX = 2000
DOCKER_DEMO_STATE_CACHE_TTL = 86400
DOCKER_DEMO_HOST_NAMES = {'app-release-test', 'gateway-prod', 'member-prod'}
DOCKER_DEMO_HOST_IPS = {'192.168.1.120', '192.168.1.121', '192.168.1.122'}


def _get_ssh_client_from_docker_host(docker_host):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=docker_host.ip_address,
        port=docker_host.ssh_port or 22,
        username=docker_host.ssh_user or 'root',
        password=docker_host.ssh_password or None,
        timeout=15,
    )
    return client


def _ssh_exec(client, cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return exit_code, out, err


def _quote_arg(value):
    return shlex.quote(str(value))


def _normalize_tail(value, default=DOCKER_LOG_TAIL_DEFAULT, max_value=DOCKER_LOG_TAIL_MAX):
    try:
        tail = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(tail, max_value))


def _docker_json_command(command):
    return f"{command} --format '{{{{json .}}}}' 2>/dev/null"


def _parse_docker_ps(raw_output):
    containers = []
    for line in raw_output.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            containers.append({
                'id': item.get('ID', ''),
                'name': item.get('Names', ''),
                'image': item.get('Image', ''),
                'status': item.get('Status', ''),
                'state': item.get('State', ''),
                'ports': item.get('Ports', ''),
                'created': item.get('CreatedAt', item.get('RunningFor', '')),
                'size': item.get('Size', ''),
            })
        except json.JSONDecodeError:
            continue
    return containers


def _parse_docker_images(raw_output):
    images = []
    for line in raw_output.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            images.append({
                'id': item.get('ID', ''),
                'repository': item.get('Repository', ''),
                'tag': item.get('Tag', ''),
                'size': item.get('Size', ''),
                'created': item.get('CreatedAt', item.get('CreatedSince', '')),
            })
        except json.JSONDecodeError:
            continue
    return images


def _ensure_image_ids(value):
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _get_docker_host(host_id):
    try:
        return DockerHost.objects.get(pk=host_id)
    except DockerHost.DoesNotExist:
        return None


def _is_demo_docker_host(docker_host):
    return (
        docker_host.name in DOCKER_DEMO_HOST_NAMES
        or docker_host.ip_address in DOCKER_DEMO_HOST_IPS
    )


def _demo_state_key(host_id):
    return f'ops:docker:demo:{host_id}'


def _demo_hex(seed, length=20):
    return hashlib.sha1(str(seed).encode('utf-8')).hexdigest()[:length]


def _demo_container_id(host_name, name):
    return f'ctr-{_demo_hex(f"{host_name}:{name}")}'


def _demo_image_id(host_name, repository, tag):
    return f'img-{_demo_hex(f"{host_name}:{repository}:{tag}")}'


def _demo_container(name, image, state, status, ports, created, host_name):
    return {
        'id': _demo_container_id(host_name, name),
        'name': name,
        'image': image,
        'status': status,
        'state': state,
        'ports': ports,
        'created': created,
        'size': '',
    }


def _demo_image(repository, tag, size, created, host_name):
    return {
        'id': _demo_image_id(host_name, repository, tag),
        'repository': repository,
        'tag': tag,
        'size': size,
        'created': created,
    }


def _build_demo_inventory(docker_host):
    host_name = docker_host.name
    common_images = [
        _demo_image('alpine', '3.20', '7.8MB', '2026-03-10 09:00:00 +0800 CST', host_name),
        _demo_image('<none>', '<none>', '183MB', '2026-03-22 14:30:00 +0800 CST', host_name),
    ]
    inventory_map = {
        'app-release-test': {
            'containers': [
                _demo_container('order-center-batch-1', 'registry.demo.local/order-center:v2.6.0', 'running', 'Up 8 hours (healthy)', '0.0.0.0:8081->8081/tcp', '2026-03-27 01:20:00 +0800 CST', host_name),
                _demo_container('order-center-batch-2', 'registry.demo.local/order-center:v2.6.0', 'running', 'Up 8 hours (healthy)', '0.0.0.0:8082->8081/tcp', '2026-03-27 01:24:00 +0800 CST', host_name),
                _demo_container('order-center-smoke', 'registry.demo.local/order-center:v2.6.0', 'exited', 'Exited (0) 7 hours ago', '', '2026-03-27 00:58:00 +0800 CST', host_name),
                _demo_container('mysql-test', 'mysql:8.0', 'running', 'Up 12 days', '0.0.0.0:3307->3306/tcp', '2026-03-15 10:00:00 +0800 CST', host_name),
                _demo_container('node-exporter', 'prom/node-exporter:v1.7.0', 'running', 'Up 21 days', '0.0.0.0:19100->9100/tcp', '2026-03-06 08:00:00 +0800 CST', host_name),
            ],
            'images': [
                _demo_image('registry.demo.local/order-center', 'v2.6.0', '428MB', '2026-03-26 20:00:00 +0800 CST', host_name),
                _demo_image('registry.demo.local/order-center', 'v2.5.4', '421MB', '2026-03-12 18:00:00 +0800 CST', host_name),
                _demo_image('mysql', '8.0', '603MB', '2026-02-18 09:00:00 +0800 CST', host_name),
                _demo_image('prom/node-exporter', 'v1.7.0', '24.3MB', '2026-02-20 13:00:00 +0800 CST', host_name),
            ] + common_images,
        },
        'gateway-prod': {
            'containers': [
                _demo_container('gateway-proxy', 'nginx:1.25-alpine', 'running', 'Up 18 days', '0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp', '2026-03-09 09:00:00 +0800 CST', host_name),
                _demo_container('member-center-failed', 'registry.demo.local/member-center:v2.4.1', 'exited', 'Exited (1) 4 hours ago', '0.0.0.0:8090->8090/tcp', '2026-03-27 04:00:00 +0800 CST', host_name),
                _demo_container('fluent-bit', 'cr.fluentbit.io/fluent/fluent-bit:2.2', 'running', 'Up 18 days', '0.0.0.0:2020->2020/tcp', '2026-03-09 09:02:00 +0800 CST', host_name),
            ],
            'images': [
                _demo_image('registry.demo.local/admin-portal', 'v1.9.3', '386MB', '2026-03-27 07:15:00 +0800 CST', host_name),
                _demo_image('registry.demo.local/member-center', 'v2.4.1', '402MB', '2026-03-27 03:45:00 +0800 CST', host_name),
                _demo_image('registry.demo.local/member-center', 'v2.3.9', '399MB', '2026-03-18 12:00:00 +0800 CST', host_name),
                _demo_image('nginx', '1.25-alpine', '54.1MB', '2026-03-09 08:55:00 +0800 CST', host_name),
                _demo_image('cr.fluentbit.io/fluent/fluent-bit', '2.2', '67.5MB', '2026-03-09 08:58:00 +0800 CST', host_name),
            ] + common_images,
        },
        'member-prod': {
            'containers': [
                _demo_container('member-openresty', 'openresty/openresty:1.25.3.1', 'running', 'Up 9 days', '0.0.0.0:8088->80/tcp', '2026-03-18 09:30:00 +0800 CST', host_name),
                _demo_container('session-redis', 'redis:7.2-alpine', 'running', 'Up 15 days', '0.0.0.0:6379->6379/tcp', '2026-03-12 10:00:00 +0800 CST', host_name),
                _demo_container('jaeger-agent', 'jaegertracing/jaeger-agent:1.56', 'restarting', 'Restarting (1) 20 seconds ago', '0.0.0.0:16874->6831/udp', '2026-03-27 08:42:00 +0800 CST', host_name),
            ],
            'images': [
                _demo_image('openresty/openresty', '1.25.3.1', '138MB', '2026-03-18 09:20:00 +0800 CST', host_name),
                _demo_image('redis', '7.2-alpine', '41.2MB', '2026-03-12 09:58:00 +0800 CST', host_name),
                _demo_image('jaegertracing/jaeger-agent', '1.56', '32.5MB', '2026-03-26 23:00:00 +0800 CST', host_name),
            ] + common_images,
        },
    }
    return inventory_map.get(host_name, {'containers': [], 'images': list(common_images)})


def _get_demo_state(docker_host):
    cache_key = _demo_state_key(docker_host.id)
    state = cache.get(cache_key)
    if state is None:
        state = _build_demo_inventory(docker_host)
        cache.set(cache_key, state, DOCKER_DEMO_STATE_CACHE_TTL)
    return state


def _set_demo_state(docker_host, state):
    cache.set(_demo_state_key(docker_host.id), state, DOCKER_DEMO_STATE_CACHE_TTL)


def _find_demo_container(state, container_id):
    return next((item for item in state.get('containers', []) if item.get('id') == container_id), None)


def _demo_logs_for_container(container):
    lines = [
        f"[INFO] container={container['name']} image={container['image']}",
        f"[INFO] state={container['state']} status={container['status']}",
    ]
    if 'order-center' in container['name']:
        lines.extend([
            '[INFO] spring boot started on port 8081',
            '[INFO] batch rollout health-check passed',
            '[WARN] traffic replay latency p95=183ms',
        ])
    elif 'member-center' in container['name']:
        lines.extend([
            '[INFO] loading config from /app/config/application-prod.yaml',
            '[ERROR] health probe failed: connect timeout to downstream profile service',
            '[INFO] container exited with code 1',
        ])
    elif container['state'] == 'restarting':
        lines.extend([
            '[WARN] previous process crashed, supervisor is restarting',
            '[INFO] retry backoff=20s',
        ])
    else:
        lines.extend([
            '[INFO] service started successfully',
            '[INFO] metrics endpoint exposed',
        ])
    return '\n'.join(lines) + '\n'


def _demo_inspect_for_container(docker_host, container):
    return {
        'Id': container['id'],
        'Name': f"/{container['name']}",
        'Image': container['image'],
        'State': {
            'Status': container['state'],
            'Running': container['state'] == 'running',
            'Restarting': container['state'] == 'restarting',
            'ExitCode': 0 if container['state'] == 'running' else 1,
        },
        'Config': {
            'Image': container['image'],
            'Hostname': docker_host.name,
            'Labels': {
                'com.sxdevops.demo': 'true',
                'com.sxdevops.host': docker_host.name,
            },
        },
        'NetworkSettings': {
            'Ports': container['ports'],
        },
        'Created': container['created'],
    }


class DockerHostViewSet(RBACPermissionMixin, viewsets.ModelViewSet):
    queryset = DockerHost.objects.all()
    serializer_class = DockerHostSerializer
    rbac_permissions = {
        'list': ['ops.docker.view'],
        'retrieve': ['ops.docker.view'],
        'create': ['ops.docker.manage'],
        'update': ['ops.docker.manage'],
        'partial_update': ['ops.docker.manage'],
        'destroy': ['ops.docker.manage'],
        'test_connection': ['ops.docker.manage'],
    }

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        docker_host = self.get_object()
        if _is_demo_docker_host(docker_host):
            docker_host.status = 'connected'
            docker_host.docker_api_version = docker_host.docker_api_version or '24.0'
            docker_host.save(update_fields=['status', 'docker_api_version', 'updated_at'])
            return Response({
                'success': True,
                'message': f'演示环境连接正常，Docker 版本: {docker_host.docker_api_version}',
            })

        try:
            client = _get_ssh_client_from_docker_host(docker_host)
            code, out, err = _ssh_exec(client, 'docker version --format "{{.Server.Version}}" 2>/dev/null')
            client.close()
            if code == 0 and out.strip():
                docker_host.status = 'connected'
                docker_host.docker_api_version = out.strip()
                docker_host.save()
                return Response({'success': True, 'message': f'连接成功，Docker 版本: {out.strip()}'})
            docker_host.status = 'error'
            docker_host.save()
            return Response({'success': False, 'message': f'Docker 未安装或无法执行: {err}'})
        except Exception as exc:
            docker_host.status = 'error'
            docker_host.save()
            return Response({'success': False, 'message': f'SSH 连接失败: {str(exc)}'})


@api_view(['GET'])
@permission_classes([IsAuthenticated, build_rbac_permission('ops.docker.view')])
def list_containers(request):
    host_id = request.query_params.get('host_id')
    if not host_id:
        return Response({'detail': '缺少 host_id 参数'}, status=400)

    docker_host = _get_docker_host(host_id)
    if not docker_host:
        return Response({'detail': 'Docker 环境不存在'}, status=404)

    if _is_demo_docker_host(docker_host):
        return Response(_get_demo_state(docker_host).get('containers', []))

    try:
        client = _get_ssh_client_from_docker_host(docker_host)
        code, out, err = _ssh_exec(client, _docker_json_command('docker ps -a'))
        client.close()
        if code != 0:
            return Response({'detail': f'Docker 命令执行失败: {err}'}, status=400)
        return Response(_parse_docker_ps(out))
    except Exception as exc:
        return Response({'detail': f'连接失败: {str(exc)}'}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated, build_rbac_permission('ops.docker.view')])
def list_images(request):
    host_id = request.query_params.get('host_id')
    if not host_id:
        return Response({'detail': '缺少 host_id 参数'}, status=400)

    docker_host = _get_docker_host(host_id)
    if not docker_host:
        return Response({'detail': 'Docker 环境不存在'}, status=404)

    if _is_demo_docker_host(docker_host):
        return Response(_get_demo_state(docker_host).get('images', []))

    try:
        client = _get_ssh_client_from_docker_host(docker_host)
        code, out, err = _ssh_exec(client, _docker_json_command('docker images'))
        client.close()
        if code != 0:
            return Response({'detail': f'Docker 命令执行失败: {err}'}, status=400)
        return Response(_parse_docker_images(out))
    except Exception as exc:
        return Response({'detail': f'连接失败: {str(exc)}'}, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated, build_rbac_permission('ops.docker.manage')])
def container_action(request, container_id):
    host_id = request.data.get('host_id')
    action_name = request.data.get('action')
    if action_name not in ('start', 'stop', 'restart'):
        return Response({'detail': '无效操作，仅支持 start / stop / restart'}, status=400)

    docker_host = _get_docker_host(host_id)
    if not docker_host:
        return Response({'detail': 'Docker 环境不存在'}, status=404)

    if _is_demo_docker_host(docker_host):
        state = _get_demo_state(docker_host)
        container = _find_demo_container(state, container_id)
        if not container:
            return Response({'detail': '演示容器不存在'}, status=404)
        if action_name == 'start':
            container['state'] = 'running'
            container['status'] = 'Up 5 seconds (healthy)'
        elif action_name == 'stop':
            container['state'] = 'exited'
            container['status'] = 'Exited (0) Just now'
        else:
            container['state'] = 'running'
            container['status'] = 'Up 2 seconds (healthy)'
        _set_demo_state(docker_host, state)
        return Response({'success': True, 'message': f'演示容器已执行 {action_name}'})

    try:
        client = _get_ssh_client_from_docker_host(docker_host)
        code, out, err = _ssh_exec(client, f'docker {action_name} {_quote_arg(container_id)} 2>&1')
        client.close()
        if code == 0:
            return Response({'success': True, 'message': f'容器 {action_name} 成功'})
        return Response({'success': False, 'message': f'操作失败: {out}{err}'}, status=400)
    except Exception as exc:
        return Response({'detail': f'连接失败: {str(exc)}'}, status=400)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, build_rbac_permission('ops.docker.manage')])
def container_remove(request, container_id):
    if is_demo_account(request.user):
        return Response({'detail': DEMO_ACCOUNT_MUTATION_MESSAGE}, status=403)
    host_id = request.query_params.get('host_id')
    docker_host = _get_docker_host(host_id)
    if not docker_host:
        return Response({'detail': 'Docker 环境不存在'}, status=404)

    if _is_demo_docker_host(docker_host):
        state = _get_demo_state(docker_host)
        containers = state.get('containers', [])
        before = len(containers)
        state['containers'] = [item for item in containers if item.get('id') != container_id]
        if len(state['containers']) == before:
            return Response({'detail': '演示容器不存在'}, status=404)
        _set_demo_state(docker_host, state)
        return Response({'success': True, 'message': '演示容器已删除'})

    try:
        client = _get_ssh_client_from_docker_host(docker_host)
        code, out, err = _ssh_exec(client, f'docker rm -f {_quote_arg(container_id)} 2>&1')
        client.close()
        if code == 0:
            return Response({'success': True, 'message': '容器已删除'})
        return Response({'success': False, 'message': f'删除失败: {out}{err}'}, status=400)
    except Exception as exc:
        return Response({'detail': f'连接失败: {str(exc)}'}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated, build_rbac_permission('ops.docker.view')])
def container_logs(request, container_id):
    host_id = request.query_params.get('host_id')
    tail = _normalize_tail(request.query_params.get('tail', DOCKER_LOG_TAIL_DEFAULT))
    docker_host = _get_docker_host(host_id)
    if not docker_host:
        return Response({'detail': 'Docker 环境不存在'}, status=404)

    if _is_demo_docker_host(docker_host):
        state = _get_demo_state(docker_host)
        container = _find_demo_container(state, container_id)
        if not container:
            return Response({'detail': '演示容器不存在'}, status=404)
        logs = _demo_logs_for_container(container).splitlines()
        return Response({'logs': '\n'.join(logs[-tail:]) + '\n'})

    try:
        client = _get_ssh_client_from_docker_host(docker_host)
        code, out, err = _ssh_exec(
            client,
            f'docker logs --tail={tail} {_quote_arg(container_id)} 2>&1',
            timeout=15,
        )
        client.close()
        return Response({'logs': out})
    except Exception as exc:
        return Response({'detail': f'获取日志失败: {str(exc)}'}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated, build_rbac_permission('ops.docker.view')])
def container_inspect(request, container_id):
    host_id = request.query_params.get('host_id')
    docker_host = _get_docker_host(host_id)
    if not docker_host:
        return Response({'detail': 'Docker 环境不存在'}, status=404)

    if _is_demo_docker_host(docker_host):
        state = _get_demo_state(docker_host)
        container = _find_demo_container(state, container_id)
        if not container:
            return Response({'detail': '演示容器不存在'}, status=404)
        return Response(_demo_inspect_for_container(docker_host, container))

    try:
        client = _get_ssh_client_from_docker_host(docker_host)
        code, out, err = _ssh_exec(client, f'docker inspect {_quote_arg(container_id)} 2>&1')
        client.close()
        if code == 0:
            try:
                data = json.loads(out)
                return Response(data[0] if data else {})
            except json.JSONDecodeError:
                return Response({'raw': out})
        return Response({'detail': f'Inspect 失败: {out}{err}'}, status=400)
    except Exception as exc:
        return Response({'detail': f'连接失败: {str(exc)}'}, status=400)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, build_rbac_permission('ops.docker.manage')])
def remove_images(request):
    if is_demo_account(request.user):
        return Response({'detail': DEMO_ACCOUNT_MUTATION_MESSAGE}, status=403)
    host_id = request.data.get('host_id') or request.query_params.get('host_id')
    image_ids = _ensure_image_ids(request.data.get('image_ids'))
    if not image_ids:
        return Response({'detail': '请选择要删除的镜像'}, status=400)

    docker_host = _get_docker_host(host_id)
    if not docker_host:
        return Response({'detail': 'Docker 环境不存在'}, status=404)

    if _is_demo_docker_host(docker_host):
        state = _get_demo_state(docker_host)
        used_images = {item.get('image') for item in state.get('containers', [])}
        removed = []
        kept = []
        for image in state.get('images', []):
            image_ref = f"{image.get('repository')}:{image.get('tag')}"
            if image.get('id') in image_ids and image_ref not in used_images:
                removed.append(image)
            else:
                kept.append(image)
        state['images'] = kept
        _set_demo_state(docker_host, state)
        skipped = len(image_ids) - len(removed)
        return Response({
            'success': True,
            'message': f'演示镜像已删除 {len(removed)} 个，跳过 {skipped} 个仍在使用的镜像',
        })

    try:
        client = _get_ssh_client_from_docker_host(docker_host)
        quoted_ids = ' '.join(_quote_arg(image_id) for image_id in image_ids)
        code, out, err = _ssh_exec(client, f'docker rmi {quoted_ids} 2>&1')
        client.close()
        if code == 0:
            return Response({'success': True, 'message': f'已删除 {len(image_ids)} 个镜像', 'output': out})
        return Response({'success': False, 'message': f'删除失败: {out}{err}'}, status=400)
    except Exception as exc:
        return Response({'detail': f'连接失败: {str(exc)}'}, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated, build_rbac_permission('ops.docker.manage')])
def prune_dangling_images(request):
    if is_demo_account(request.user):
        return Response({'detail': DEMO_ACCOUNT_MUTATION_MESSAGE}, status=403)
    host_id = request.data.get('host_id')
    docker_host = _get_docker_host(host_id)
    if not docker_host:
        return Response({'detail': 'Docker 环境不存在'}, status=404)

    if _is_demo_docker_host(docker_host):
        state = _get_demo_state(docker_host)
        before = len(state.get('images', []))
        state['images'] = [
            item for item in state.get('images', [])
            if item.get('repository') != '<none>' and item.get('tag') != '<none>'
        ]
        reclaimed = before - len(state['images'])
        _set_demo_state(docker_host, state)
        return Response({'success': True, 'message': f'演示环境已清理 {reclaimed} 个悬空镜像'})

    try:
        client = _get_ssh_client_from_docker_host(docker_host)
        code, out, err = _ssh_exec(client, 'docker image prune -f 2>&1')
        client.close()
        if code == 0:
            return Response({'success': True, 'message': '悬空镜像已清理', 'output': out})
        return Response({'success': False, 'message': f'清理失败: {out}{err}'}, status=400)
    except Exception as exc:
        return Response({'detail': f'连接失败: {str(exc)}'}, status=400)
