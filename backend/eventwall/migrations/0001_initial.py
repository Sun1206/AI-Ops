from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='EventRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('occurred_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='发生时间')),
                ('module', models.CharField(db_index=True, max_length=32, verbose_name='模块')),
                ('category', models.CharField(db_index=True, max_length=32, verbose_name='分类')),
                ('action', models.CharField(db_index=True, max_length=32, verbose_name='动作')),
                ('result', models.CharField(choices=[('success', '成功'), ('failed', '失败'), ('partial', '部分成功'), ('pending', '待处理'), ('rejected', '已拒绝')], db_index=True, default='success', max_length=16, verbose_name='结果')),
                ('severity', models.CharField(choices=[('info', '信息'), ('warning', '提示'), ('danger', '高风险')], default='info', max_length=16, verbose_name='风险级别')),
                ('title', models.CharField(max_length=255, verbose_name='事件标题')),
                ('summary', models.CharField(blank=True, default='', max_length=255, verbose_name='事件摘要')),
                ('detail', models.TextField(blank=True, default='', verbose_name='详情')),
                ('actor_type', models.CharField(choices=[('user', '用户'), ('system', '系统')], default='user', max_length=16, verbose_name='操作者类型')),
                ('actor_username', models.CharField(blank=True, db_index=True, default='', max_length=64, verbose_name='操作者')),
                ('actor_display', models.CharField(blank=True, default='', max_length=128, verbose_name='操作者展示名')),
                ('source_type', models.CharField(choices=[('http', 'HTTP'), ('async', '异步任务'), ('scheduler', '调度器'), ('system', '系统'), ('seed', '演示数据'), ('websocket', 'WebSocket')], default='http', max_length=16, verbose_name='来源类型')),
                ('request_method', models.CharField(blank=True, default='', max_length=12, verbose_name='请求方法')),
                ('source_path', models.CharField(blank=True, default='', max_length=255, verbose_name='来源路径')),
                ('ip_address', models.CharField(blank=True, default='', max_length=64, verbose_name='IP 地址')),
                ('correlation_id', models.CharField(blank=True, db_index=True, default='', max_length=128, verbose_name='关联链路')),
                ('resource_module', models.CharField(blank=True, default='', max_length=32, verbose_name='资源模块')),
                ('resource_type', models.CharField(blank=True, db_index=True, default='', max_length=64, verbose_name='资源类型')),
                ('resource_id', models.CharField(blank=True, db_index=True, default='', max_length=64, verbose_name='资源 ID')),
                ('resource_name', models.CharField(blank=True, db_index=True, default='', max_length=255, verbose_name='资源名称')),
                ('business_line', models.CharField(blank=True, default='', max_length=64, verbose_name='业务线')),
                ('environment', models.CharField(blank=True, default='', max_length=32, verbose_name='环境')),
                ('tags', models.JSONField(blank=True, default=list, verbose_name='标签')),
                ('related_resources', models.JSONField(blank=True, default=list, verbose_name='关联资源')),
                ('changes', models.JSONField(blank=True, default=dict, verbose_name='变更内容')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='元数据')),
                ('is_demo', models.BooleanField(default=False, verbose_name='演示数据')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('parent_event', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='eventwall.eventrecord', verbose_name='父事件')),
            ],
            options={
                'verbose_name': '事件记录',
                'verbose_name_plural': '事件记录',
                'ordering': ['-occurred_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='eventrecord',
            index=models.Index(fields=['module', 'occurred_at'], name='eventwall_e_module__482151_idx'),
        ),
        migrations.AddIndex(
            model_name='eventrecord',
            index=models.Index(fields=['module', 'result', 'occurred_at'], name='eventwall_e_module__7ab027_idx'),
        ),
        migrations.AddIndex(
            model_name='eventrecord',
            index=models.Index(fields=['resource_type', 'resource_id', 'occurred_at'], name='eventwall_e_resourc_0fd175_idx'),
        ),
        migrations.AddIndex(
            model_name='eventrecord',
            index=models.Index(fields=['actor_username', 'occurred_at'], name='eventwall_e_actor_u_85ce0f_idx'),
        ),
    ]
