from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aiops', '0013_agent_task_generation_copy'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiopsskill',
            name='applicable_actions',
            field=models.JSONField(blank=True, default=list, verbose_name='适用 Action'),
        ),
        migrations.AddField(
            model_name='aiopsskill',
            name='builtin_tools',
            field=models.JSONField(blank=True, default=list, verbose_name='内置工具'),
        ),
        migrations.AddField(
            model_name='aiopsskill',
            name='category',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='分类'),
        ),
        migrations.AddField(
            model_name='aiopsskill',
            name='examples',
            field=models.JSONField(blank=True, default=list, verbose_name='示例问题'),
        ),
        migrations.AddField(
            model_name='aiopsskill',
            name='max_iterations',
            field=models.PositiveIntegerField(default=0, verbose_name='最大轮次'),
        ),
        migrations.AddField(
            model_name='aiopsskill',
            name='output_contract',
            field=models.JSONField(blank=True, default=dict, verbose_name='输出约束'),
        ),
        migrations.AddField(
            model_name='aiopsskill',
            name='recommended_tools',
            field=models.JSONField(blank=True, default=list, verbose_name='推荐工具'),
        ),
        migrations.AddField(
            model_name='aiopsskill',
            name='risk_level',
            field=models.CharField(
                choices=[
                    ('read_only', '只读'),
                    ('draft', '草稿'),
                    ('write', '写入'),
                    ('execute', '执行'),
                ],
                default='read_only',
                max_length=16,
                verbose_name='风险等级',
            ),
        ),
    ]
