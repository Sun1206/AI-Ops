from datetime import timedelta

from django.utils import timezone

from ops.models import LogEntry

from .common import backdate


LOG_TEMPLATES = (
    ('order-service', '订单查询完成 status=200 latency_ms={latency}'),
    ('payment-worker', '支付回调处理完成 channel=alipay latency_ms={latency}'),
    ('member-api', '会员资料读取完成 cache=hit latency_ms={latency}'),
    ('gateway-nginx', 'POST /api/v1/orders status=200 upstream_time={latency}ms'),
    ('mysql-primary', 'slow_query table=orders rows_examined={rows} duration_ms={latency}'),
    ('kubelet', 'container health probe completed result=success latency_ms={latency}'),
)


def _level(index):
    if index % 17 == 0:
        return 'error'
    if index % 7 == 0:
        return 'warning'
    return 'info'


def seed_log_data(stats, runtime):
    now = timezone.now()
    hosts = runtime['hosts']
    logs = []

    for index in range(600):
        request_id = f'OPS-{index + 1:06d}'
        service, template = LOG_TEMPLATES[index % len(LOG_TEMPLATES)]
        level = _level(index)
        latency = 18 + (index * 29) % 1680
        detail = template.format(latency=latency, rows=800 + index * 17)
        if level == 'warning':
            detail = f'performance threshold approached {detail}'
        elif level == 'error':
            detail = f'retry succeeded after transient timeout {detail}'
        event_time = now - timedelta(
            days=index % 30,
            hours=(index * 7) % 24,
            minutes=(index * 13) % 60,
            seconds=index % 57,
        )
        log = LogEntry.objects.filter(
            message__contains=f'request_id={request_id}',
        ).order_by('pk').first()
        if log is None:
            log = LogEntry.objects.create(
                level=level,
                service=service,
                message=(
                    f'{detail} request_id={request_id} '
                    f'trace_id={index + 1:032x} env=prod'
                ),
                host=hosts[index % len(hosts)],
            )
            stats.record(True)
            log._production_seed_created = True
        else:
            stats.record(False)
            log._production_seed_created = False
        backdate(log, timestamp=event_time)
        logs.append(log)

    return logs
