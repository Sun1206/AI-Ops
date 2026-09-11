from datetime import timedelta

from django.utils import timezone

from ops.models import (
    Alert,
    AlertAction,
    AlertAggregationRule,
    AlertEscalationPolicy,
    AlertMuteRule,
    AlertNotificationChannel,
    AlertNotificationLog,
    AlertNotificationRule,
    AlertRecipient,
    AlertRecipientGroup,
)

from .common import backdate, get_or_create_first, get_or_create_json_key


RECIPIENTS = [
    ('王涛', 'SRE 值班负责人'),
    ('李俊', '交易平台应用运维'),
    ('周敏', '支付平台应用运维'),
    ('陈芳', '质量与发布保障'),
    ('韩梅', '数据平台运维'),
    ('赵磊', '数据库管理员'),
    ('孙博', '中间件运维'),
    ('吴迪', '安全响应工程师'),
]

GROUPS = {
    'SRE 一线值班': [0, 3],
    '交易平台值班': [1, 2],
    '数据平台值班': [4, 5],
    '基础设施值班': [0, 6, 7],
}

CHANNELS = [
    ('生产告警邮件', 'email', {'smtp_host': 'smtp.ops.internal', 'to': 'oncall@corp.internal'}),
    ('SRE 钉钉群', 'dingtalk', {'webhook_url': 'https://notify.ops.internal/dingtalk'}),
    ('应用值班飞书群', 'feishu', {'webhook_url': 'https://notify.ops.internal/feishu'}),
    ('基础设施企微群', 'wecom', {'webhook_url': 'https://notify.ops.internal/wecom'}),
]

RULES = [
    ('生产严重告警', 'critical', [{'key': 'environment', 'op': '=', 'value': 'prod'}], 0),
    ('交易平台告警', 'warning', [{'key': 'business_line', 'op': '=', 'value': '交易平台'}], 1),
    ('支付平台告警', 'warning', [{'key': 'service', 'op': '=~', 'value': 'payment.*'}], 1),
    ('数据平台告警', 'warning', [{'key': 'business_line', 'op': '=', 'value': '数据平台'}], 2),
    ('基础设施告警', 'warning', [{'key': 'resource_type', 'op': 'in', 'value': ['node', 'database']}], 3),
]

HISTORY_DAYS = [1, 2, 3, 4, 5, 6, 7, 9, 12, 15, 18, 21, 25, 30, 36, 45, 55, 65, 75, 88]

ALERT_PROVIDERS = [
    ('Prometheus Alertmanager', 'prometheus'),
    ('夜莺监控平台', 'nightingale'),
    ('Zabbix 生产监控', 'zabbix'),
    ('阿里云云监控', 'aliyun'),
]

ALERT_TEMPLATES = [
    ('订单接口 P99 延迟超过阈值', 'order-service', '交易平台', 'application', 'http_request_duration_p99', '订单请求 P99 延迟持续高于 800ms'),
    ('支付异步任务积压', 'payment-worker', '支付平台', 'queue', 'payment_queue_depth', '支付回调队列积压超过容量水位'),
    ('会员服务错误率升高', 'member-api', '会员中心', 'application', 'http_error_rate', '会员权益查询错误率持续升高'),
    ('数据库连接池使用率过高', 'mysql-primary', '交易平台', 'database', 'db_pool_usage', '主库连接池使用率超过 90%'),
    ('Kubernetes 节点磁盘压力', 'kubelet', '基础设施', 'node', 'node_disk_pressure', '生产集群节点出现磁盘压力'),
    ('网关上游 5xx 增加', 'gateway-nginx', '接入网关', 'gateway', 'upstream_5xx_rate', '网关上游服务 5xx 比例超过阈值'),
    ('Redis 热点 Key 流量突增', 'redis-cluster', '基础设施', 'cache', 'redis_hotkey_qps', '热点 Key 请求量超过正常基线'),
    ('数据同步链路延迟', 'data-sync', '数据平台', 'job', 'sync_lag_seconds', '实时数据同步延迟超过五分钟'),
]


def _seed_alert_events(stats, base, now):
    alerts = []
    for index in range(260):
        title, service, business_line, resource_type, metric_name, message = (
            ALERT_TEMPLATES[index % len(ALERT_TEMPLATES)]
        )
        source, source_type = ALERT_PROVIDERS[index % len(ALERT_PROVIDERS)]
        status_value = (
            'active'
            if index % 5 in {0, 1}
            else 'resolved'
            if index % 5 in {2, 3}
            else 'closed'
        )
        level = 'critical' if index % 7 == 0 else ('info' if index % 11 == 0 else 'warning')
        event_time = now - timedelta(
            days=index % 30,
            hours=(index * 5) % 24,
            minutes=(index * 17) % 60,
            seconds=index % 53,
        )
        last_received_at = event_time + timedelta(minutes=index % 23)
        alert = get_or_create_json_key(
            Alert,
            json_field='raw_payload',
            seed_key=f'production-alert-{index + 1:03d}',
            defaults={
                'title': title,
                'level': level,
                'status': status_value,
                'source': source,
                'source_type': source_type,
                'external_id': f'OPS-{source_type.upper()}-{index + 1:06d}',
                'fingerprint': f'{source_type}:{service}:{metric_name}:{index + 1:03d}',
                'group_key': f'prod/{business_line}/{service}',
                'message': message,
                'is_acknowledged': status_value != 'active' and index % 3 != 0,
                'acknowledged_by': (
                    RECIPIENTS[index % len(RECIPIENTS)][0]
                    if status_value != 'active' and index % 3 != 0
                    else ''
                ),
                'acknowledged_at': (
                    event_time + timedelta(minutes=8 + index % 20)
                    if status_value != 'active' and index % 3 != 0
                    else None
                ),
                'host': base['host'],
                'service': service,
                'environment': 'prod' if index % 8 else 'staging',
                'cluster': 'prod-shanghai-k8s',
                'namespace': 'production',
                'region': 'cn-shanghai',
                'business_line': business_line,
                'resource_type': resource_type,
                'resource': f'{service}-{index % 12 + 1:02d}',
                'metric_name': metric_name,
                'labels': {
                    'service': service,
                    'environment': 'prod',
                    'severity': level,
                },
                'annotations': {
                    'summary': title,
                    'description': message,
                },
                'raw_payload': {
                    'seed_namespace': 'production-alerts',
                    'receiver': 'platform-alert-center',
                },
                'starts_at': event_time,
                'ends_at': (
                    event_time + timedelta(minutes=18 + index % 90)
                    if status_value != 'active'
                    else None
                ),
                'last_received_at': last_received_at,
                'occurrence_count': 1 + index % 19,
                'closed_at': (
                    event_time + timedelta(minutes=30 + index % 100)
                    if status_value == 'closed'
                    else None
                ),
            },
            stats=stats,
        )
        backdate(
            alert,
            created_at=event_time,
            updated_at=last_received_at,
        )
        alerts.append(alert)
    return alerts


def seed_alerting(stats, base):
    recipients = []
    for index, (name, description) in enumerate(RECIPIENTS, start=1):
        recipients.append(get_or_create_first(
            AlertRecipient,
            {'name': name},
            {
                'phone': '',
                'email': f'oncall{index}@corp.internal',
                'dingtalk_user_id': '',
                'feishu_user_id': '',
                'wecom_user_id': '',
                'is_enabled': True,
                'description': description,
            },
            stats,
        ))

    groups = {}
    for name, indexes in GROUPS.items():
        group = get_or_create_first(
            AlertRecipientGroup,
            {'name': name},
            {'description': f'{name}告警响应组', 'is_enabled': True},
            stats,
        )
        if group._production_seed_created:
            group.recipients.set([recipients[index] for index in indexes])
        groups[name] = group

    channels = []
    for name, channel_type, config in CHANNELS:
        channels.append(get_or_create_first(
            AlertNotificationChannel,
            {'name': name, 'channel_type': channel_type},
            {
                'is_enabled': False,
                'send_resolved': True,
                'timeout_seconds': 8,
                'config': config,
                'template_title': '[{{ level }}] {{ title }}',
                'template_body': '{{ message }}\n服务: {{ service }}\n环境: {{ environment }}',
            },
            stats,
        ))

    aggregation = AlertAggregationRule.objects.order_by('pk').first()
    escalation = AlertEscalationPolicy.objects.order_by('pk').first()
    rules = []
    group_values = list(groups.values())
    for index, (name, level, matchers, group_index) in enumerate(RULES):
        rule = get_or_create_first(
            AlertNotificationRule,
            {'name': name},
            {
                'is_enabled': False,
                'matchers': matchers,
                'min_level': level,
                'aggregation_rule': aggregation,
                'escalation_policy': escalation,
                'notify_on_fire': True,
                'notify_on_resolved': True,
                'notify_on_escalation': True,
                'description': f'{name}分派策略',
            },
            stats,
        )
        if rule._production_seed_created:
            rule.channels.set([channels[index % len(channels)]])
            rule.recipient_groups.set([group_values[group_index]])
        rules.append(rule)

    now = timezone.now()
    mute_specs = [
        (
            '生产数据库变更窗口',
            [{'key': 'resource_type', 'op': '=', 'value': 'database'}],
            3,
            '主从切换与参数调整',
        ),
        (
            '数据平台批处理窗口',
            [{'key': 'business_line', 'op': '=', 'value': '数据平台'}],
            1,
            '月度批处理资源扩容',
        ),
    ]
    for name, matchers, days, reason in mute_specs:
        get_or_create_first(
            AlertMuteRule,
            {'name': name},
            {
                'is_enabled': True,
                'matchers': matchers,
                'starts_at': now - timedelta(hours=2),
                'ends_at': now + timedelta(days=days),
                'reason': reason,
                'created_by': 'SRE-王涛',
            },
            stats,
        )

    alerts = _seed_alert_events(stats, base, now)
    notification_statuses = ['success', 'success', 'skipped', 'error']
    for index in range(20):
        status = notification_statuses[index % len(notification_statuses)]
        created_at = now - timedelta(days=HISTORY_DAYS[index], minutes=index * 7)
        log = get_or_create_json_key(
            AlertNotificationLog,
            json_field='request_payload',
            seed_key=f'notification-history-{index + 1:02d}',
            defaults={
                'alert': alerts[index % len(alerts)],
                'rule': rules[index % len(rules)],
                'channel': channels[index % len(channels)],
                'action': 'resolved' if index % 5 == 0 else 'fire',
                'status': status,
                'recipient_summary': group_values[index % len(group_values)].name,
                'request_payload': {'source': 'alert-center', 'attempt': index % 3 + 1},
                'response_body': 'accepted' if status == 'success' else '',
                'error_message': 'channel temporarily unavailable' if status == 'error' else '',
                'sent_at': created_at,
            },
            stats=stats,
        )
        backdate(log, created_at=created_at)

    action_types = ['acknowledge', 'claim', 'comment', 'escalate', 'resolve', 'close']
    notes = ('确认影响范围并开始处置', '补充链路与日志证据', '恢复后持续观察三十分钟')
    for index in range(15):
        action = get_or_create_json_key(
            AlertAction,
            json_field='metadata',
            seed_key=f'alert-action-history-{index + 1:02d}',
            defaults={
                'alert': alerts[index % len(alerts)],
                'action': action_types[index % len(action_types)],
                'actor': recipients[index % len(recipients)].name,
                'note': notes[index % len(notes)],
                'metadata': {
                    'source': 'alert-center',
                    'shift': 'primary' if index % 2 == 0 else 'backup',
                },
            },
            stats=stats,
        )
        backdate(action, created_at=now - timedelta(days=HISTORY_DAYS[index]))

    return {
        'recipients': recipients,
        'groups': groups,
        'channels': channels,
        'rules': rules,
        'alerts': alerts,
    }
