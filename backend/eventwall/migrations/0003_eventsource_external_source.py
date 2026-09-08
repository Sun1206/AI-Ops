from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eventwall', '0002_eventrecord_application'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.SlugField(max_length=64, unique=True, verbose_name='事件源编码')),
                ('name', models.CharField(max_length=128, verbose_name='事件源名称')),
                ('source_kind', models.CharField(choices=[('builtin', '平台内置'), ('external', '外部接入')], max_length=16, verbose_name='事件源类别')),
                ('source_type', models.CharField(choices=[('builtin_workorder', '工单系统'), ('builtin_task', '任务中心'), ('builtin_k8s', 'K8s 事件'), ('jira', 'Jira'), ('jenkins', 'Jenkins'), ('argocd', 'ArgoCD'), ('gitlab', 'GitLab'), ('custom', '自定义事件源')], max_length=32, verbose_name='事件源类型')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='说明')),
                ('enabled', models.BooleanField(default=False, verbose_name='启用状态')),
                ('status', models.CharField(choices=[('healthy', '健康'), ('warning', '待关注'), ('disabled', '已停用'), ('not_configured', '未配置')], default='not_configured', max_length=32, verbose_name='健康状态')),
                ('endpoint_url', models.URLField(blank=True, default='', max_length=512, verbose_name='外部地址')),
                ('auth_type', models.CharField(choices=[('none', '无需认证'), ('token', 'Token'), ('basic', 'Basic Auth'), ('webhook', 'Webhook Token')], default='webhook', max_length=16, verbose_name='认证方式')),
                ('token_hash', models.CharField(blank=True, default='', max_length=64, verbose_name='接入令牌哈希')),
                ('token_preview', models.CharField(blank=True, default='', max_length=24, verbose_name='令牌预览')),
                ('config', models.JSONField(blank=True, default=dict, verbose_name='采集配置')),
                ('field_mapping', models.JSONField(blank=True, default=dict, verbose_name='字段映射')),
                ('last_sync_at', models.DateTimeField(blank=True, null=True, verbose_name='最近同步时间')),
                ('last_event_at', models.DateTimeField(blank=True, null=True, verbose_name='最近事件时间')),
                ('last_error', models.CharField(blank=True, default='', max_length=255, verbose_name='最近错误')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '事件源',
                'verbose_name_plural': '事件源',
                'ordering': ['source_kind', 'source_type', 'code'],
            },
        ),
        migrations.AlterField(
            model_name='eventrecord',
            name='source_type',
            field=models.CharField(choices=[('http', 'HTTP'), ('async', '异步任务'), ('scheduler', '调度器'), ('system', '系统'), ('seed', '演示数据'), ('websocket', 'WebSocket'), ('external', 'External')], default='http', max_length=16, verbose_name='来源类型'),
        ),
        migrations.AddIndex(
            model_name='eventsource',
            index=models.Index(fields=['source_kind', 'source_type'], name='eventwall_e_source__b65c96_idx'),
        ),
        migrations.AddIndex(
            model_name='eventsource',
            index=models.Index(fields=['enabled', 'status'], name='eventwall_e_enabled_985ed8_idx'),
        ),
    ]
