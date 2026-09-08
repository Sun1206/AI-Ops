from django.conf import settings
from django.db import migrations


def seed_log_datasources(apps, schema_editor):
    LogDataSource = apps.get_model('ops', 'LogDataSource')
    configs = getattr(settings, 'LOG_PROVIDER_CONFIGS', {}) or {}
    seeds = [
        ('loki', 'Default Loki', bool(configs.get('loki', {}).get('endpoint'))),
        ('elk', 'Default ELK', bool(configs.get('elk', {}).get('endpoint'))),
        (
            'sls',
            'Default Aliyun SLS',
            bool(configs.get('sls', {}).get('endpoint') and configs.get('sls', {}).get('project')),
        ),
    ]

    for provider, name, should_create in seeds:
        if not should_create:
            continue
        if LogDataSource.objects.filter(provider=provider).exists():
            continue
        LogDataSource.objects.create(
            name=name,
            provider=provider,
            description='System seeded datasource',
            config=configs.get(provider, {}),
            is_enabled=True,
            is_default=True,
        )


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ('ops', '0008_logdatasource'),
    ]

    operations = [
        migrations.RunPython(seed_log_datasources, noop),
    ]
