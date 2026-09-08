from django.db import migrations


def refresh_demo_log_datasources(apps, schema_editor):
    LogDataSource = apps.get_model('ops', 'LogDataSource')

    rename_map = {
        'ELK Demo': 'ELK 演示（免认证）',
        'SLS Demo': 'SLS 演示（杭州）',
    }
    for old_name, new_name in rename_map.items():
        LogDataSource.objects.filter(name=old_name).update(name=new_name)

    templates = [
        {
            'name': 'ELK 演示（免认证）',
            'provider': 'elk',
            'description': '演示用 ELK 数据源，模拟生产应用与安全日志，无需真实连接。',
            'config': {
                'endpoint': 'https://demo-elastic.example.com:9200',
                'auth_type': 'none',
                'index_pattern': 'logs-demo-*',
                'time_field': '@timestamp',
                'message_fields': 'message,log,msg',
                'demo_mode': True,
                'demo_indices': ['logs-demo-app-2026.03.15', 'logs-demo-security-2026.03.15'],
            },
            'is_enabled': True,
            'is_default': False,
        },
        {
            'name': 'ELK 演示（API Key 模板）',
            'provider': 'elk',
            'description': '演示用 ELK API Key 模板，便于展示认证方式和查询效果。',
            'config': {
                'endpoint': 'https://demo-elastic-secure.example.com:9200',
                'auth_type': 'api_key',
                'api_key': 'demo-api-key',
                'index_pattern': 'logs-demo-*',
                'time_field': '@timestamp',
                'message_fields': 'message,log,msg',
                'demo_mode': True,
                'demo_indices': ['logs-demo-app-2026.03.15', 'logs-demo-security-2026.03.15'],
            },
            'is_enabled': True,
            'is_default': False,
        },
        {
            'name': 'SLS 演示（杭州）',
            'provider': 'sls',
            'description': '演示用阿里云 SLS 数据源，模拟杭州地域业务日志。',
            'config': {
                'endpoint': 'cn-hangzhou.log.aliyuncs.com',
                'project': 'demo-hz-project',
                'logstore': 'demo-hz-logstore',
                'topic': 'order',
                'access_key_id': 'demo-ak-id',
                'access_key_secret': 'demo-ak-secret',
                'demo_mode': True,
                'demo_logstores': ['demo-hz-logstore', 'demo-hz-audit'],
            },
            'is_enabled': True,
            'is_default': False,
        },
        {
            'name': 'SLS 演示（上海）',
            'provider': 'sls',
            'description': '演示用阿里云 SLS 数据源，模拟上海地域认证与用户日志。',
            'config': {
                'endpoint': 'cn-shanghai.log.aliyuncs.com',
                'project': 'demo-sh-project',
                'logstore': 'demo-sh-logstore',
                'topic': 'auth',
                'access_key_id': 'demo-ak-id',
                'access_key_secret': 'demo-ak-secret',
                'demo_mode': True,
                'demo_logstores': ['demo-sh-logstore', 'demo-sh-auth'],
            },
            'is_enabled': True,
            'is_default': False,
        },
    ]

    for item in templates:
        LogDataSource.objects.update_or_create(
            name=item['name'],
            defaults=item,
        )


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ('ops', '0010_seed_demo_logdatasources'),
    ]

    operations = [
        migrations.RunPython(refresh_demo_log_datasources, noop),
    ]
