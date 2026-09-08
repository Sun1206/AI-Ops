from eventwall.models import EventEnvironment
from ops.models import TaskResource, TaskResourceGroup

from .common import get_or_create_first


ENVIRONMENTS = [
    ('生产环境', 'prod', 10),
    ('预发布环境', 'staging', 20),
    ('开发环境', 'dev', 30),
]

SYSTEMS = [
    ('交易平台', 'trade', 'prod', 10),
    ('支付平台', 'payment', 'prod', 20),
    ('会员中心', 'member', 'prod', 30),
    ('数据平台', 'data', 'prod', 40),
    ('基础设施', 'infra', 'prod', 50),
]

RESOURCE_NAMES = [
    'order-api-01',
    'order-api-02',
    'inventory-api-01',
    'gateway-01',
    'payment-api-01',
    'payment-worker-01',
    'member-api-01',
    'member-worker-01',
    'airflow-scheduler-01',
    'airflow-worker-01',
    'data-sync-01',
    'report-api-01',
    'mysql-primary-01',
    'mysql-replica-01',
    'redis-cluster-01',
    'mq-broker-01',
    'prod-order-workload',
    'prod-payment-workload',
    'staging-gateway-workload',
    'dev-data-workload',
]


def seed_task_resources(stats, base):
    event_envs = {item.code: item for item in EventEnvironment.objects.all()}
    envs = {}
    for name, code, order in ENVIRONMENTS:
        envs[code] = get_or_create_first(
            TaskResourceGroup,
            {'group_type': 'environment', 'parent': None, 'name': name},
            {
                'code': code,
                'event_environment': event_envs.get(code),
                'description': f'{name}资源底座',
                'sort_order': order,
                'created_by': 'ops.reader',
                'updated_by': 'ops.reader',
            },
            stats,
        )
    systems = {}
    for env_code, environment in envs.items():
        for name, code, _default_env, order in SYSTEMS:
            systems[f'{env_code}:{code}'] = get_or_create_first(
                TaskResourceGroup,
                {'group_type': 'system', 'parent': environment, 'name': name},
                {
                    'code': f'{code}-{env_code}',
                    'description': f'{environment.name}{name}资源',
                    'sort_order': order,
                    'created_by': 'ops.reader',
                    'updated_by': 'ops.reader',
                },
                stats,
            )
    system_codes = tuple(item[1] for item in SYSTEMS)
    owners = ('应用运维-李俊', 'SRE-王涛', '数据平台-韩梅')
    for index, name in enumerate(RESOURCE_NAMES):
        is_k8s = index >= 16
        env_code = 'prod' if index < 18 else ('staging' if index == 18 else 'dev')
        system_code = system_codes[index % len(system_codes)]
        status = 'warning' if index in {10, 17} else ('inactive' if index == 15 else 'active')
        get_or_create_first(
            TaskResource,
            {
                'name': name,
                'resource_type': 'k8s' if is_k8s else 'host',
                'environment': envs[env_code],
                'system': systems[f'{env_code}:{system_code}'],
            },
            {
                'status': status,
                'ip_address': None if is_k8s else f'10.{10 + index // 8}.{1 + index % 8}.{20 + index}',
                'ssh_port': 22,
                'ssh_user': 'ops',
                'ssh_password': '',
                'cluster': base['cluster'] if is_k8s else None,
                'namespace': 'production' if env_code == 'prod' else env_code,
                'owner': owners[index % len(owners)],
                'description': f'{name}运行资源',
                'metadata': {
                    'region': 'cn-shanghai',
                    'zone': f'zone-{index % 3 + 1}',
                    'service_tier': 'critical' if env_code == 'prod' else 'standard',
                },
                'created_by': 'ops.reader',
                'updated_by': 'ops.reader',
            },
            stats,
        )
    return {'environments': envs, 'systems': systems}
