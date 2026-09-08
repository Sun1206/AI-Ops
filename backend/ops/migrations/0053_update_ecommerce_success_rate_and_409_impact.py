from django.db import migrations


SERVICE_SUCCESS_QUERY = '100 * sum by (service) (rate(ecommerce_http_requests_total{namespace="{namespace}",service=~"{services}",status!~"[45].."}[{window}])) / clamp_min(sum by (service) (rate(ecommerce_http_requests_total{namespace="{namespace}",service=~"{services}"}[{window}])), 0.000001)'
PATH_SUCCESS_QUERY = '100 * sum by (service,path) (rate(ecommerce_http_requests_total{namespace="{namespace}",service=~"{services}",status!~"[45].."}[{window}])) / clamp_min(sum by (service,path) (rate(ecommerce_http_requests_total{namespace="{namespace}",service=~"{services}"}[{window}])), 0.000001)'

DEFAULT_AFFECTED_SERVICES = [
    {
        'service_id': 'api-gateway',
        'interface_id': 'gateway-checkout',
        'metric_label': 'Checkout 409占比',
        'message': '下单入口返回 409，需要继续下钻库存与订单链路。',
    },
    {
        'service_id': 'order',
        'interface_id': 'order-create',
        'metric_label': '订单受影响',
        'message': '订单创建被库存冲突拒绝，需要核对订单写入前后的库存校验。',
    },
    {
        'service_id': 'inventory',
        'interface_id': 'inventory-availability',
        'metric_label': '库存冲突率',
        'message': '库存可用性校验返回冲突，优先检查库存余量与补货任务。',
    },
]


def update_ecommerce_success_rate_and_409_impact(apps, schema_editor):
    SystemPostureSystem = apps.get_model('ops', 'SystemPostureSystem')
    queryset = SystemPostureSystem.objects.filter(name__in=['电商交易核心', '交易系统核心'])
    for system in queryset:
        rule_config = system.rule_config if isinstance(system.rule_config, dict) else {}
        next_config = dict(rule_config)

        prometheus = next_config.get('prometheus') if isinstance(next_config.get('prometheus'), dict) else {}
        next_prometheus = dict(prometheus)
        series = next_prometheus.get('series') if isinstance(next_prometheus.get('series'), dict) else {}
        next_series = dict(series)
        service_success = next_series.get('service_success_rate') if isinstance(next_series.get('service_success_rate'), dict) else {}
        path_success = next_series.get('path_success_rate') if isinstance(next_series.get('path_success_rate'), dict) else {}
        if service_success:
            next_service_success = dict(service_success)
            next_service_success['query'] = SERVICE_SUCCESS_QUERY
            next_series['service_success_rate'] = next_service_success
        if path_success:
            next_path_success = dict(path_success)
            next_path_success['query'] = PATH_SUCCESS_QUERY
            next_series['path_success_rate'] = next_path_success
        if next_series:
            next_prometheus['series'] = next_series
            next_config['prometheus'] = next_prometheus

        rules = next_config.get('root_cause_rules') if isinstance(next_config.get('root_cause_rules'), list) else []
        next_rules = []
        for rule in rules:
            if not isinstance(rule, dict):
                next_rules.append(rule)
                continue
            next_rule = dict(rule)
            if next_rule.get('id') == 'inventory-conflict' or next_rule.get('target_service_id') == 'inventory':
                next_rule['count_as_fault'] = True
                next_rule.setdefault('critical_rate', 1)
                next_rule.setdefault('target_service_id', 'inventory')
                next_rule.setdefault('target_interface_id', 'inventory-availability')
                next_rule['affected_services'] = DEFAULT_AFFECTED_SERVICES
            next_rules.append(next_rule)
        if next_rules:
            next_config['root_cause_rules'] = next_rules

        if next_config != rule_config:
            system.rule_config = next_config
            system.save(update_fields=['rule_config'])


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0052_rename_systemposture_core_metric_field'),
    ]

    operations = [
        migrations.RunPython(update_ecommerce_success_rate_and_409_impact, migrations.RunPython.noop),
    ]
