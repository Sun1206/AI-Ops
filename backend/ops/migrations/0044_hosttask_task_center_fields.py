from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0043_systempostureslahistory'),
    ]

    operations = [
        migrations.AddField(
            model_name='hosttask',
            name='correlation_id',
            field=models.CharField(blank=True, db_index=True, default='', max_length=128, verbose_name='关联链路'),
        ),
        migrations.AddField(
            model_name='hosttask',
            name='lifecycle_status',
            field=models.CharField(choices=[('pending_confirmation', '待确认'), ('pending_approval', '待审批'), ('pending_execution', '待执行'), ('running', '执行中'), ('success', '执行成功'), ('partial', '部分成功'), ('failed', '执行失败'), ('canceled', '已取消')], default='pending_execution', max_length=32, verbose_name='生命周期状态'),
        ),
        migrations.AddField(
            model_name='hosttask',
            name='risk_level',
            field=models.CharField(choices=[('low', '低'), ('medium', '中'), ('high', '高'), ('critical', '极高')], default='low', max_length=16, verbose_name='风险等级'),
        ),
        migrations.AddField(
            model_name='hosttask',
            name='source_context',
            field=models.JSONField(blank=True, default=dict, verbose_name='来源上下文'),
        ),
        migrations.AlterField(
            model_name='hosttask',
            name='trigger_source',
            field=models.CharField(choices=[('manual', '手动触发'), ('schedule', '定时触发'), ('aiops', 'AIOps 生成'), ('event_center', '事件中心触发'), ('api', 'API 触发')], default='manual', max_length=16, verbose_name='触发来源'),
        ),
    ]
