from django.db import migrations


def seed_loki_demo_datasource(apps, schema_editor):
    LogDataSource = apps.get_model('ops', 'LogDataSource')
    LogDataSource.objects.update_or_create(
        name='Loki 演示（免连接）',
        defaults={
            'provider': 'loki',
            'description': '演示用 Loki 数据源，内置网关、支付、认证等示例日志，无需真实连接。',
            'config': {
                'endpoint': 'http://demo-loki.example.com:3100',
                'demo_mode': True,
            },
            'is_enabled': True,
            'is_default': False,
        },
    )


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ('ops', '0011_refresh_demo_logdatasources'),
    ]

    operations = [
        migrations.RunPython(seed_loki_demo_datasource, noop),
    ]
