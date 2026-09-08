from django.db import migrations


def seed_alert_center_defaults(apps, schema_editor):
    AlertIntegration = apps.get_model('ops', 'AlertIntegration')
    AlertAggregationRule = apps.get_model('ops', 'AlertAggregationRule')
    AlertInhibitionRule = apps.get_model('ops', 'AlertInhibitionRule')
    AlertEscalationPolicy = apps.get_model('ops', 'AlertEscalationPolicy')

    integrations = [
        ('Prometheus Alertmanager', 'prometheus'),
        ('Zabbix', 'zabbix'),
        ('夜莺', 'nightingale'),
        ('阿里云监控', 'aliyun'),
        ('通用 Webhook', 'generic'),
    ]
    for name, provider in integrations:
        AlertIntegration.objects.get_or_create(
            provider=provider,
            name=name,
            defaults={
                'is_enabled': True,
                'description': f'{name} 告警 Webhook 接入源',
            },
        )

    aggregation, _ = AlertAggregationRule.objects.get_or_create(
        name='默认按来源环境服务聚合',
        defaults={
            'is_enabled': True,
            'group_by': ['source_type', 'environment', 'service', 'cluster', 'namespace', 'resource'],
            'window_minutes': 5,
            'repeat_interval_minutes': 30,
            'description': '按来源、环境、服务和资源收敛重复告警通知。',
        },
    )

    AlertInhibitionRule.objects.get_or_create(
        name='严重告警抑制同服务低优先级',
        defaults={
            'is_enabled': True,
            'source_matchers': [{'key': 'level', 'op': '==', 'value': 'critical'}],
            'target_matchers': [{'key': 'level', 'op': '!=', 'value': 'critical'}],
            'equal_labels': ['environment', 'service', 'resource'],
            'duration_minutes': 60,
            'description': '同环境同服务同资源出现严重告警时，暂时抑制低优先级告警。',
        },
    )

    AlertEscalationPolicy.objects.get_or_create(
        name='严重告警 30/60 分钟升级',
        defaults={
            'is_enabled': True,
            'matchers': [{'key': 'level', 'op': '==', 'value': 'critical'}],
            'levels': [
                {'name': '一线升级', 'after_minutes': 30, 'channel_ids': []},
                {'name': '负责人升级', 'after_minutes': 60, 'channel_ids': []},
            ],
            'repeat_interval_minutes': 30,
            'description': '严重告警持续未恢复时按 30/60 分钟推进升级。',
        },
    )


def remove_alert_center_defaults(apps, schema_editor):
    AlertIntegration = apps.get_model('ops', 'AlertIntegration')
    AlertAggregationRule = apps.get_model('ops', 'AlertAggregationRule')
    AlertInhibitionRule = apps.get_model('ops', 'AlertInhibitionRule')
    AlertEscalationPolicy = apps.get_model('ops', 'AlertEscalationPolicy')

    AlertIntegration.objects.filter(provider__in=['prometheus', 'zabbix', 'nightingale', 'aliyun', 'generic']).delete()
    AlertAggregationRule.objects.filter(name='默认按来源环境服务聚合').delete()
    AlertInhibitionRule.objects.filter(name='严重告警抑制同服务低优先级').delete()
    AlertEscalationPolicy.objects.filter(name='严重告警 30/60 分钟升级').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0034_alert_center_refactor'),
    ]

    operations = [
        migrations.RunPython(seed_alert_center_defaults, remove_alert_center_defaults),
    ]
