from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0018_host_admin_user_host_business_line_host_description_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='HostTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='任务名称')),
                ('task_type', models.CharField(choices=[('check_connection', 'SSH 连通性校验'), ('refresh_metrics', '主机信息刷新'), ('run_command', '批量命令执行'), ('service_status', '服务状态巡检')], max_length=32, verbose_name='任务类型')),
                ('status', models.CharField(choices=[('pending', '待执行'), ('running', '执行中'), ('success', '全部成功'), ('partial', '部分成功'), ('failed', '执行失败')], default='pending', max_length=16, verbose_name='执行状态')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='任务说明')),
                ('payload', models.JSONField(blank=True, default=dict, verbose_name='任务参数')),
                ('selection_filters', models.JSONField(blank=True, default=dict, verbose_name='筛选条件')),
                ('target_snapshot', models.JSONField(blank=True, default=list, verbose_name='目标快照')),
                ('execution_strategy', models.CharField(choices=[('continue', '失败继续'), ('stop_on_error', '失败即停')], default='continue', max_length=20, verbose_name='执行策略')),
                ('timeout_seconds', models.PositiveIntegerField(default=15, verbose_name='超时时间(秒)')),
                ('target_count', models.PositiveIntegerField(default=0, verbose_name='目标数量')),
                ('success_count', models.PositiveIntegerField(default=0, verbose_name='成功数量')),
                ('failed_count', models.PositiveIntegerField(default=0, verbose_name='失败数量')),
                ('skipped_count', models.PositiveIntegerField(default=0, verbose_name='跳过数量')),
                ('created_by', models.CharField(default='system', max_length=64, verbose_name='创建人')),
                ('summary', models.CharField(blank=True, default='', max_length=255, verbose_name='执行摘要')),
                ('started_at', models.DateTimeField(blank=True, null=True, verbose_name='开始时间')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='完成时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '主机任务',
                'verbose_name_plural': '主机任务',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='HostTaskExecution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('host_name', models.CharField(default='', max_length=128, verbose_name='主机名快照')),
                ('host_ip', models.GenericIPAddressField(verbose_name='主机 IP 快照')),
                ('status', models.CharField(choices=[('success', '成功'), ('failed', '失败'), ('skipped', '跳过')], default='success', max_length=16, verbose_name='执行状态')),
                ('command', models.TextField(blank=True, default='', verbose_name='执行命令')),
                ('output', models.TextField(blank=True, default='', verbose_name='输出内容')),
                ('error_message', models.TextField(blank=True, default='', verbose_name='错误信息')),
                ('duration_ms', models.PositiveIntegerField(default=0, verbose_name='耗时(毫秒)')),
                ('started_at', models.DateTimeField(blank=True, null=True, verbose_name='开始时间')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='完成时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('host', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_executions', to='ops.host', verbose_name='目标主机')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='executions', to='ops.hosttask', verbose_name='主机任务')),
            ],
            options={
                'verbose_name': '主机任务执行记录',
                'verbose_name_plural': '主机任务执行记录',
                'ordering': ['id'],
            },
        ),
    ]
