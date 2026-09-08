from django.db import migrations


def seed_demo_log_datasources(apps, schema_editor):
    LogDataSource = apps.get_model('ops', 'LogDataSource')

    demos = [
        {
            'name': 'ELK Demo',
            'provider': 'elk',
            'description': 'Demo datasource. Update endpoint and auth before use.',
            'config': {
                'endpoint': 'https://demo-elastic.example.com:9200',
                'auth_type': 'none',
                'index_pattern': 'logs-*',
                'time_field': '@timestamp',
                'message_fields': 'message,log,msg',
            },
            'is_enabled': True,
            'is_default': False,
        },
        {
            'name': 'SLS Demo',
            'provider': 'sls',
            'description': 'Demo datasource. Replace project, logstore, and AK/SK before use.',
            'config': {
                'endpoint': 'cn-hangzhou.log.aliyuncs.com',
                'project': 'demo-project',
                'logstore': 'demo-logstore',
                'topic': '',
                'access_key_id': 'demo-ak',
                'access_key_secret': 'demo-sk',
            },
            'is_enabled': True,
            'is_default': False,
        },
    ]

    for item in demos:
        LogDataSource.objects.get_or_create(
            name=item['name'],
            defaults=item,
        )


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ('ops', '0009_seed_logdatasources'),
    ]

    operations = [
        migrations.RunPython(seed_demo_log_datasources, noop),
    ]
