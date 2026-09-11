from datetime import timedelta

from django.utils import timezone

from ops.models import Deployment, Host

from .common import backdate, get_or_create_first


SYSTEMS = [
    ('order', '交易平台'),
    ('payment', '支付平台'),
    ('member', '会员中心'),
    ('data', '数据平台'),
    ('gateway', '接入网关'),
    ('infra', '基础设施'),
]

OWNERS = ('李俊', '周敏', '韩梅', '赵磊')
SUBMITTERS = ('release.bot', '李俊', '周敏')
APPROVERS = ('王涛', '陈芳')
DEPLOYMENT_STATUSES = ['running'] * 11 + ['stopped'] * 3 + ['failed', 'rejected', 'removed']


def _host_status(index):
    if index % 17 == 0:
        return 'offline'
    if index % 9 == 0:
        return 'warning'
    return 'online'


def _usage(index, status, normal_base, normal_span):
    if status == 'warning':
        return 82 + index % 12
    if status == 'offline':
        return index % 8
    return normal_base + index % normal_span


def seed_runtime_data(stats, base):
    del base
    now = timezone.now()
    hosts = []
    for index in range(72):
        code, business_line = SYSTEMS[index % len(SYSTEMS)]
        status = _host_status(index)
        host = get_or_create_first(
            Host,
            {'hostname': f'prod-{code}-{index + 1:03d}'},
            {
                'ip_address': (
                    f'10.{20 + index // 48}.{(index // 16) % 3 + 1}.'
                    f'{20 + index % 200}'
                ),
                'business_line': business_line,
                'environment': 'prod',
                'admin_user': OWNERS[index % len(OWNERS)],
                'os_type': 'Alibaba Cloud Linux 3',
                'description': f'{business_line}生产节点',
                'status': status,
                'cpu_usage': _usage(index, status, 28, 47),
                'memory_usage': _usage(index + 3, status, 35, 42),
                'disk_usage': _usage(index + 7, status, 31, 45),
                'ssh_password': '',
            },
            stats,
        )
        hosts.append(host)

    deployments = []
    for index in range(180):
        code, business_line = SYSTEMS[index % len(SYSTEMS)]
        status = DEPLOYMENT_STATUSES[index % len(DEPLOYMENT_STATUSES)]
        event_time = now - timedelta(
            days=index % 30,
            minutes=(index * 37) % 1440,
        )
        approval_status = 'rejected' if status == 'rejected' else 'approved'
        finished_at = (
            event_time + timedelta(minutes=6 + index % 18)
            if status not in {'pending', 'deploying'}
            else None
        )
        deployment = get_or_create_first(
            Deployment,
            {'deploy_dir': f'/srv/releases/{code}/history-{index + 1:03d}'},
            {
                'app_name': f'{code}-service',
                'business_line': business_line,
                'version': f'2026.09.{index % 12 + 1}.{index + 100}',
                'image': (
                    f'registry.ops.internal/{code}/service:'
                    f'2026.09.{index % 12 + 1}'
                ),
                'environment': 'prod' if index % 5 else 'test',
                'deploy_mode': 'docker_compose',
                'status': status,
                'approval_status': approval_status,
                'action_type': 'rollback' if index % 23 == 0 else 'deploy',
                'release_strategy': ('standard', 'canary', 'batch')[index % 3],
                'submitter': SUBMITTERS[index % len(SUBMITTERS)],
                'deployer': 'release.bot',
                'approver': APPROVERS[index % len(APPROVERS)],
                'approval_comment': (
                    '检查通过，按发布窗口执行'
                    if approval_status == 'approved'
                    else '变更窗口冲突，调整后重新提交'
                ),
                'change_summary': f'{business_line}常规版本发布',
                'description': '自动化发布流水线执行记录',
                'env_config': {'ENVIRONMENT': 'production'},
                'deploy_log': (
                    'image pulled; health check passed; traffic switched'
                    if status in {'running', 'stopped', 'removed'}
                    else 'deployment validation failed'
                    if status == 'failed'
                    else ''
                ),
                'release_name': f'{code}-service',
                'replicas': 2 + index % 5,
                'container_port': 8000 + index % 10,
                'service_port': 80,
                'canary_percent': (10, 20, 30)[index % 3],
                'batch_total': 3 if index % 3 == 2 else 1,
                'batch_current': 3 if index % 3 == 2 else 1,
                'batch_size': 2 + index % 4,
                'strategy_config': {'health_check': '/healthz'},
                'host': hosts[index % len(hosts)],
                'approved_at': (
                    event_time - timedelta(minutes=12)
                    if approval_status == 'approved'
                    else None
                ),
                'executed_at': (
                    event_time if approval_status == 'approved' else None
                ),
                'finished_at': finished_at,
                'execution_count': 0 if status == 'rejected' else 1,
                'is_current': False,
            },
            stats,
        )
        backdate(deployment, deployed_at=event_time)
        deployments.append(deployment)

    return {'hosts': hosts, 'deployments': deployments}
