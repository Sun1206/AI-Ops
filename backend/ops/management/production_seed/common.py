from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.utils import timezone

from ops.models import Alert, Host, K8sCluster, LogDataSource


@dataclass
class SeedStats:
    created: int = 0
    reused: int = 0

    def record(self, created):
        if created:
            self.created += 1
        else:
            self.reused += 1


def get_or_create_first(model, lookup, defaults, stats):
    obj = model.objects.filter(**lookup).order_by('pk').first()
    if obj is None:
        obj = model.objects.create(**lookup, **defaults)
        stats.record(True)
        obj._production_seed_created = True
    else:
        stats.record(False)
        obj._production_seed_created = False
    return obj


def get_or_create_json_key(model, *, json_field, seed_key, defaults, stats):
    obj = model.objects.filter(**{f'{json_field}__seed_key': seed_key}).order_by('pk').first()
    if obj is None:
        payload = dict(defaults.get(json_field) or {})
        payload['seed_key'] = seed_key
        values = {**defaults, json_field: payload}
        obj = model.objects.create(**values)
        stats.record(True)
        obj._production_seed_created = True
    else:
        stats.record(False)
        obj._production_seed_created = False
    return obj


def backdate(obj, **timestamps):
    if getattr(obj, '_production_seed_created', False):
        type(obj).objects.filter(pk=obj.pk).update(**timestamps)


def resolve_base_objects(stats):
    user, created = get_user_model().objects.get_or_create(
        username='ops.reader',
        defaults={'first_name': '运维', 'last_name': '值班', 'is_active': True},
    )
    stats.record(created)
    host = get_or_create_first(
        Host,
        {'hostname': 'order-api-ecs-01'},
        {
            'ip_address': '10.10.1.10', 'business_line': '交易平台',
            'environment': 'prod', 'admin_user': '应用运维-李俊',
            'os_type': 'Alibaba Cloud Linux 3', 'status': 'online',
            'cpu_usage': 43, 'memory_usage': 57, 'disk_usage': 61,
            'ssh_password': '',
        },
        stats,
    )
    alert = get_or_create_json_key(
        Alert,
        json_field='raw_payload',
        seed_key='operations-order-latency-alert',
        defaults={
            'title': '订单服务下游依赖延迟升高',
            'level': 'critical', 'source': 'Prometheus',
            'source_type': 'prometheus',
            'message': '库存依赖 P99 延迟连续五分钟超过阈值',
            'host': host, 'service': 'order-service', 'environment': 'prod',
            'fingerprint': 'operations-order-latency',
            'last_received_at': timezone.now(),
            'raw_payload': {'source': 'alertmanager'},
        },
        stats=stats,
    )
    log_source = get_or_create_first(
        LogDataSource,
        {'name': '生产日志中心'},
        {
            'provider': 'loki', 'description': '生产应用与基础设施日志',
            'config': {'base_url': 'http://loki.ops.internal:3100'},
            'is_enabled': False, 'is_default': True,
        },
        stats,
    )
    cluster = get_or_create_first(
        K8sCluster,
        {'name': 'prod-shanghai-k8s'},
        {
            'api_server': 'https://10.30.0.10:6443', 'kubeconfig': '',
            'status': 'disconnected', 'description': '交易平台生产集群',
        },
        stats,
    )
    return {
        'user': user,
        'host': host,
        'alert': alert,
        'log_source': log_source,
        'cluster': cluster,
    }
