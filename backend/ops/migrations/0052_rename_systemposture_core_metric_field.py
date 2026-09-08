from django.db import migrations


def normalize_core_metric_json(apps, schema_editor):
    legacy_key = 'north' + '_star'
    SystemPostureSystem = apps.get_model('ops', 'SystemPostureSystem')
    SystemPostureSLAHistory = apps.get_model('ops', 'SystemPostureSLAHistory')

    for system in SystemPostureSystem.objects.all():
        rule_config = system.rule_config if isinstance(system.rule_config, dict) else {}
        if legacy_key not in rule_config:
            continue
        next_config = dict(rule_config)
        if 'core_metric' not in next_config and isinstance(next_config.get(legacy_key), dict):
            next_config['core_metric'] = next_config.get(legacy_key)
        next_config.pop(legacy_key, None)
        system.rule_config = next_config
        system.save(update_fields=['rule_config'])

    for record in SystemPostureSLAHistory.objects.all():
        snapshot = record.snapshot if isinstance(record.snapshot, dict) else {}
        if legacy_key not in snapshot:
            continue
        next_snapshot = dict(snapshot)
        if 'core_metric' not in next_snapshot and isinstance(next_snapshot.get(legacy_key), dict):
            next_snapshot['core_metric'] = next_snapshot.get(legacy_key)
        next_snapshot.pop(legacy_key, None)
        record.snapshot = next_snapshot
        record.save(update_fields=['snapshot'])


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0051_use_checkout_success_core_metric'),
    ]

    operations = [
        migrations.RenameField(
            model_name='systemposturesystem',
            old_name='north' + '_star',
            new_name='core_metric',
        ),
        migrations.RunPython(normalize_core_metric_json, migrations.RunPython.noop),
    ]
