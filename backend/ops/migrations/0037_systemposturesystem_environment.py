from django.db import migrations, models


def normalize_firemap_json_defaults(apps, schema_editor):
    FireMapSystem = apps.get_model('ops', 'FireMapSystem')
    list_fields = ['keywords', 'metrics', 'service_specs', 'dependencies', 'playbook']
    for field in list_fields:
        FireMapSystem.objects.filter(**{f'{field}__isnull': True}).update(**{field: []})
    FireMapSystem.objects.filter(north_star__isnull=True).update(north_star={})
    FireMapSystem.objects.filter(rule_config__isnull=True).update(rule_config={})


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0036_alert_multi_claims'),
    ]

    operations = [
        migrations.RunPython(normalize_firemap_json_defaults, migrations.RunPython.noop),
        migrations.AddField(
            model_name='firemapsystem',
            name='environment',
            field=models.CharField(blank=True, default='prod', max_length=32, verbose_name='环境'),
        ),
    ]
