from django.db import migrations, models


NEW_WELCOME_MESSAGE = '你好，我可以帮你结合平台上下文查询资源、根因分析、生成待执行任务等。'
OLD_WELCOME_MESSAGES = {
    '你好，我可以帮你结合平台上下文查询资源、分析告警、成本分析、生成待执行任务等。',
    '你好，我可以帮你结合平台上下文查询资源、分析告警、定位根因、汇总日志/链路/事件证据，并生成待确认的运维任务草稿。',
}


def normalize_agent_config(apps, schema_editor):
    agent_config = apps.get_model('aiops', 'AIOpsAgentConfig')
    for config in agent_config.objects.all():
        update_fields = []
        if not config.welcome_message or config.welcome_message in OLD_WELCOME_MESSAGES:
            config.welcome_message = NEW_WELCOME_MESSAGE
            update_fields.append('welcome_message')
        if config.require_confirmation is not True:
            config.require_confirmation = True
            update_fields.append('require_confirmation')
        if update_fields:
            config.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('aiops', '0012_remove_task_resource_system_scope'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aiopsagentconfig',
            name='allow_action_execution',
            field=models.BooleanField(default=True, verbose_name='允许生成待执行任务'),
        ),
        migrations.AlterField(
            model_name='aiopsagentconfig',
            name='require_confirmation',
            field=models.BooleanField(default=True, verbose_name='任务中心确认'),
        ),
        migrations.AlterField(
            model_name='aiopsagentconfig',
            name='welcome_message',
            field=models.CharField(blank=True, default=NEW_WELCOME_MESSAGE, max_length=255, verbose_name='欢迎语'),
        ),
        migrations.RunPython(normalize_agent_config, migrations.RunPython.noop),
    ]
