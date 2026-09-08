from django.db import migrations, models


def enable_default_log_to_grafana(apps, schema_editor):
    ObservabilityDataSourceLink = apps.get_model('ops', 'ObservabilityDataSourceLink')
    ObservabilityDataSourceLink.objects.filter(name='电商 k3s Loki ↔ Tempo').update(log_to_grafana_enabled=True)


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0029_observabilitydatasourcelink_grafana'),
    ]

    operations = [
        migrations.AddField(
            model_name='observabilitydatasourcelink',
            name='log_to_grafana_enabled',
            field=models.BooleanField(default=True, verbose_name='日志跳看板'),
        ),
        migrations.RunPython(enable_default_log_to_grafana, noop),
    ]
