from django.db import migrations


def use_checkout_success_core_metric(apps, schema_editor):
    SystemPostureSystem = apps.get_model('ops', 'SystemPostureSystem')
    queryset = SystemPostureSystem.objects.filter(name__in=['电商交易核心', '交易系统核心'])
    for system in queryset:
        rule_config = system.rule_config if isinstance(system.rule_config, dict) else {}
        prometheus = rule_config.get('prometheus') if isinstance(rule_config.get('prometheus'), dict) else {}
        scalars = prometheus.get('scalars') if isinstance(prometheus.get('scalars'), dict) else {}
        if 'checkout_success_rate' not in scalars:
            continue
        next_config = dict(rule_config)
        next_config['core_metric'] = {
            'metric': 'checkout_success_rate',
            'label': '下单成功率',
            'target': 90,
            'unit': '%',
            'direction': 'higher',
        }
        next_config.pop('north' + '_star', None)
        system.rule_config = next_config
        system.save(update_fields=['rule_config'])


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0050_force_ecommerce_409_fault_threshold'),
    ]

    operations = [
        migrations.RunPython(use_checkout_success_core_metric, migrations.RunPython.noop),
    ]
