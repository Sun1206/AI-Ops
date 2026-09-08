from django.db import migrations


def force_ecommerce_409_fault_threshold(apps, schema_editor):
    SystemPostureSystem = apps.get_model('ops', 'SystemPostureSystem')
    queryset = SystemPostureSystem.objects.filter(name__in=['电商交易核心', '交易系统核心'])
    for system in queryset:
        rule_config = system.rule_config if isinstance(system.rule_config, dict) else {}
        rules = rule_config.get('root_cause_rules')
        if not isinstance(rules, list):
            continue
        changed = False
        normalized = []
        for rule in rules:
            if not isinstance(rule, dict):
                normalized.append(rule)
                continue
            next_rule = dict(rule)
            if next_rule.get('id') == 'inventory-conflict' or next_rule.get('target_service_id') == 'inventory':
                next_rule['count_as_fault'] = True
                next_rule['min_rate'] = next_rule.get('min_rate', 1)
                next_rule['critical_rate'] = 1
                changed = True
            normalized.append(next_rule)
        if changed:
            rule_config = dict(rule_config)
            rule_config['root_cause_rules'] = normalized
            system.rule_config = rule_config
            system.save(update_fields=['rule_config'])


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0049_populate_ecommerce_posture_rule_json'),
    ]

    operations = [
        migrations.RunPython(force_ecommerce_409_fault_threshold, migrations.RunPython.noop),
    ]
