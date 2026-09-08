from django.db import migrations


def force_tracing_datasources_live(apps, schema_editor):
    TracingDataSource = apps.get_model('ops', 'TracingDataSource')
    for datasource in TracingDataSource.objects.all():
        config = dict(datasource.config or {})
        if config.get('demo_mode') is False:
            continue
        config['demo_mode'] = False
        datasource.config = config
        datasource.save(update_fields=['config', 'updated_at'])


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0031_observabilitydatasourcelink_grafana_reverse'),
    ]

    operations = [
        migrations.RunPython(force_tracing_datasources_live, noop),
    ]
