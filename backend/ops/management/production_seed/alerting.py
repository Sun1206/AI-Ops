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

    alerts = [base['alert']]
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
    }
