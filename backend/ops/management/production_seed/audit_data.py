from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from eventwall.models import EventRecord

from .common import backdate, get_or_create_first


AUDIT_TEMPLATES = (
    {
        'module': 'ops', 'category': 'deployment', 'action': 'deploy',
        'title': '生产服务发布执行完成', 'resource_type': 'deployment',
        'resource_name': 'order-service', 'source_type': EventRecord.SOURCE_ASYNC,
    },
    {
        'module': 'ops', 'category': 'task', 'action': 'execute',
        'title': '批量主机巡检任务执行完成', 'resource_type': 'host_task',
        'resource_name': '生产主机日常巡检', 'source_type': EventRecord.SOURCE_SCHEDULER,
    },
    {
        'module': 'rbac', 'category': 'permission', 'action': 'update',
        'title': '运维角色权限策略更新', 'resource_type': 'role',
        'resource_name': '生产运维工程师', 'source_type': EventRecord.SOURCE_HTTP,
    },
    {
        'module': 'sqlaudit', 'category': 'execution', 'action': 'approve',
        'title': '数据库变更工单审批通过', 'resource_type': 'sql_order',
        'resource_name': '订单库索引优化', 'source_type': EventRecord.SOURCE_HTTP,
    },
    {
        'module': 'aiops', 'category': 'analysis', 'action': 'query',
        'title': '智能助手完成故障上下文分析', 'resource_type': 'aiops_session',
        'resource_name': '生产故障分析会话', 'source_type': EventRecord.SOURCE_SYSTEM,
    },
    {
        'module': 'ops', 'category': 'configuration', 'action': 'update',
        'title': '监控告警路由配置更新', 'resource_type': 'alert_route',
        'resource_name': '核心业务告警路由', 'source_type': EventRecord.SOURCE_HTTP,
    },
)


def seed_audit_data(stats, base):
    EventRecord.objects.filter(
        Q(source_type=EventRecord.SOURCE_SEED) | Q(is_demo=True),
    ).update(source_type=EventRecord.SOURCE_SYSTEM, is_demo=False)

    now = timezone.now()
    actors = (
        ('release.bot', '发布机器人'),
        ('SRE-王涛', '王涛'),
        ('DBA-陈芳', '陈芳'),
        (base['user'].username, '运维值班'),
    )
    results = [EventRecord.RESULT_SUCCESS] * 8 + [
        EventRecord.RESULT_FAILED,
        EventRecord.RESULT_PARTIAL,
    ]
    events = []

    for index in range(300):
        template = AUDIT_TEMPLATES[index % len(AUDIT_TEMPLATES)]
        actor_username, actor_display = actors[index % len(actors)]
        result = results[index % len(results)]
        severity = (
            EventRecord.SEVERITY_DANGER
            if result == EventRecord.RESULT_FAILED
            else EventRecord.SEVERITY_WARNING
            if result == EventRecord.RESULT_PARTIAL
            else EventRecord.SEVERITY_INFO
        )
        event_time = now - timedelta(
            days=index % 30,
            hours=(index * 11) % 24,
            minutes=(index * 19) % 60,
            seconds=(index * 23) % 60,
        )
        correlation_id = f'prod-audit-{index + 1:04d}'
        event = get_or_create_first(
            EventRecord,
            {'correlation_id': correlation_id},
            {
                'occurred_at': event_time,
                'module': template['module'],
                'category': template['category'],
                'action': template['action'],
                'result': result,
                'severity': severity,
                'title': template['title'],
                'summary': f"{template['resource_name']}操作已记录，执行结果为 {result}",
                'detail': '平台已保存请求参数、执行状态和资源关联信息。',
                'actor_type': (
                    EventRecord.ACTOR_SYSTEM
                    if template['source_type'] in {
                        EventRecord.SOURCE_ASYNC,
                        EventRecord.SOURCE_SCHEDULER,
                        EventRecord.SOURCE_SYSTEM,
                    }
                    else EventRecord.ACTOR_USER
                ),
                'actor_username': actor_username,
                'actor_display': actor_display,
                'source_type': template['source_type'],
                'request_method': 'POST' if template['source_type'] == EventRecord.SOURCE_HTTP else '',
                'source_path': f"/api/{template['module']}/{template['action']}/",
                'ip_address': f'10.60.{index % 8}.{20 + index % 200}',
                'resource_module': template['module'],
                'resource_type': template['resource_type'],
                'resource_id': f'OPS-{index + 1000}',
                'resource_name': template['resource_name'],
                'business_line': ('交易平台', '支付平台', '数据平台')[index % 3],
                'environment': 'prod' if index % 8 else 'staging',
                'application': template['resource_name'],
                'tags': ['operations', 'audit', template['module']],
                'related_resources': [],
                'changes': {'sequence': index + 1},
                'metadata': {'origin': 'operations-platform'},
                'is_demo': False,
            },
            stats,
        )
        backdate(event, occurred_at=event_time, created_at=event_time)
        events.append(event)

    return events
