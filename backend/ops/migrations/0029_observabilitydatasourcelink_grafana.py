from django.db import migrations, models


DEFAULT_GRAFANA_VARIABLE_MAPPINGS = [
    {'trace_tag': 'service.name', 'variable': 'service'},
    {'trace_tag': 'service.namespace', 'variable': 'namespace'},
]


def seed_default_grafana_link(apps, schema_editor):
    ObservabilityDataSourceLink = apps.get_model('ops', 'ObservabilityDataSourceLink')
    ObservabilityDataSourceLink.objects.filter(name='电商 k3s Loki ↔ Tempo').update(
        trace_to_grafana_enabled=True,
        grafana_dashboard_key='apm-overview',
        grafana_variable_mappings=DEFAULT_GRAFANA_VARIABLE_MAPPINGS,
    )


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0028_observabilitydatasourcelink'),
    ]

    operations = [
        migrations.AddField(
            model_name='observabilitydatasourcelink',
            name='grafana_dashboard_key',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='Grafana 看板 Key'),
        ),
        migrations.AddField(
            model_name='observabilitydatasourcelink',
            name='grafana_variable_mappings',
            field=models.JSONField(blank=True, default=list, verbose_name='Grafana 变量映射'),
        ),
        migrations.AddField(
            model_name='observabilitydatasourcelink',
            name='trace_to_grafana_enabled',
            field=models.BooleanField(default=True, verbose_name='链路跳看板'),
        ),
        migrations.RunPython(seed_default_grafana_link, noop),
    ]
