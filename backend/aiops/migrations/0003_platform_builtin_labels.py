from django.db import migrations, models


def migrate_demo_mcp_type(apps, schema_editor):
    AIOpsMCPServer = apps.get_model('aiops', 'AIOpsMCPServer')
    AIOpsMCPServer.objects.filter(server_type='demo').update(server_type='platform_builtin')


def rollback_platform_builtin_mcp_type(apps, schema_editor):
    AIOpsMCPServer = apps.get_model('aiops', 'AIOpsMCPServer')
    AIOpsMCPServer.objects.filter(server_type='platform_builtin').update(server_type='demo')


class Migration(migrations.Migration):

    dependencies = [
        ('aiops', '0002_aiopsagentconfig_enabled_mcp_server_ids_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_demo_mcp_type, rollback_platform_builtin_mcp_type),
        migrations.AlterField(
            model_name='aiopsmcpserver',
            name='server_type',
            field=models.CharField(
                choices=[('http', 'HTTP'), ('stdio', 'STDIO'), ('platform_builtin', '平台内置')],
                default='http',
                max_length=16,
                verbose_name='类型',
            ),
        ),
        migrations.AlterField(
            model_name='aiopsmcpserver',
            name='tool_whitelist',
            field=models.JSONField(blank=True, default=list, verbose_name='启用工具'),
        ),
        migrations.AlterField(
            model_name='aiopsskill',
            name='source_type',
            field=models.CharField(
                choices=[('inline', '平台内置'), ('local', '本地文件')],
                default='inline',
                max_length=16,
                verbose_name='来源类型',
            ),
        ),
    ]
