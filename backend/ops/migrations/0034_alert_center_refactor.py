# Generated for the alert center refactor.

import django.db.models.deletion
import django.utils.timezone
import ops.models
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0033_firemapsystem'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AlertAction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('webhook', 'Webhook 接入'), ('notify', '发送通知'), ('acknowledge', '确认'), ('claim', '认领'), ('unclaim', '取消认领'), ('mute', '屏蔽'), ('escalate', '升级'), ('resolve', '恢复'), ('close', '关闭'), ('reopen', '重新打开'), ('comment', '备注')], max_length=32, verbose_name='动作')),
                ('actor', models.CharField(blank=True, default='', max_length=128, verbose_name='操作人')),
                ('note', models.CharField(blank=True, default='', max_length=255, verbose_name='说明')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='元数据')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
            ],
            options={
                'verbose_name': '告警动作',
                'verbose_name_plural': '告警动作',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AlertAggregationRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='聚合规则名称')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('matchers', models.JSONField(blank=True, default=list, verbose_name='匹配条件')),
                ('group_by', models.JSONField(blank=True, default=list, verbose_name='聚合维度')),
                ('window_minutes', models.PositiveIntegerField(default=5, verbose_name='聚合窗口分钟')),
                ('repeat_interval_minutes', models.PositiveIntegerField(default=30, verbose_name='重复通知间隔分钟')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='说明')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '告警聚合规则',
                'verbose_name_plural': '告警聚合规则',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='AlertEscalationPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='升级策略名称')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('matchers', models.JSONField(blank=True, default=list, verbose_name='匹配条件')),
                ('levels', models.JSONField(blank=True, default=list, verbose_name='升级层级')),
                ('repeat_interval_minutes', models.PositiveIntegerField(default=30, verbose_name='升级间隔分钟')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='说明')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '告警升级策略',
                'verbose_name_plural': '告警升级策略',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='AlertInhibitionRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='抑制规则名称')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('source_matchers', models.JSONField(blank=True, default=list, verbose_name='源告警匹配')),
                ('target_matchers', models.JSONField(blank=True, default=list, verbose_name='目标告警匹配')),
                ('equal_labels', models.JSONField(blank=True, default=list, verbose_name='相同标签')),
                ('duration_minutes', models.PositiveIntegerField(default=60, verbose_name='抑制时长分钟')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='说明')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '告警抑制规则',
                'verbose_name_plural': '告警抑制规则',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='AlertIntegration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='接入源名称')),
                ('provider', models.CharField(choices=[('prometheus', 'Prometheus Alertmanager'), ('zabbix', 'Zabbix'), ('nightingale', '夜莺'), ('aliyun', '阿里云监控'), ('generic', '通用 Webhook')], max_length=32, verbose_name='接入类型')),
                ('token', models.CharField(default=ops.models.generate_alert_token, max_length=64, unique=True, verbose_name='接入令牌')),
                ('secret', models.CharField(blank=True, default='', max_length=255, verbose_name='签名密钥')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('default_labels', models.JSONField(blank=True, default=dict, verbose_name='默认标签')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='说明')),
                ('last_received_at', models.DateTimeField(blank=True, null=True, verbose_name='最近接收时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '告警接入源',
                'verbose_name_plural': '告警接入源',
                'ordering': ['provider', 'name'],
            },
        ),
        migrations.CreateModel(
            name='AlertInteractionToken',
            fields=[
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='交互令牌')),
                ('action', models.CharField(choices=[('webhook', 'Webhook 接入'), ('notify', '发送通知'), ('acknowledge', '确认'), ('claim', '认领'), ('unclaim', '取消认领'), ('mute', '屏蔽'), ('escalate', '升级'), ('resolve', '恢复'), ('close', '关闭'), ('reopen', '重新打开'), ('comment', '备注')], max_length=32, verbose_name='动作')),
                ('provider', models.CharField(blank=True, default='', max_length=32, verbose_name='来源渠道')),
                ('expires_at', models.DateTimeField(verbose_name='过期时间')),
                ('used_at', models.DateTimeField(blank=True, null=True, verbose_name='使用时间')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='元数据')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
            ],
            options={
                'verbose_name': '告警卡片交互令牌',
                'verbose_name_plural': '告警卡片交互令牌',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AlertMuteRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='屏蔽规则名称')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('matchers', models.JSONField(blank=True, default=list, verbose_name='匹配条件')),
                ('starts_at', models.DateTimeField(blank=True, null=True, verbose_name='开始时间')),
                ('ends_at', models.DateTimeField(blank=True, null=True, verbose_name='结束时间')),
                ('reason', models.CharField(blank=True, default='', max_length=255, verbose_name='原因')),
                ('created_by', models.CharField(blank=True, default='', max_length=64, verbose_name='创建人')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '告警屏蔽规则',
                'verbose_name_plural': '告警屏蔽规则',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AlertNotificationChannel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='渠道名称')),
                ('channel_type', models.CharField(choices=[('sms', '短信'), ('voice', '语音'), ('email', '邮件'), ('dingtalk', '钉钉'), ('feishu', '飞书'), ('wecom', '企微')], max_length=32, verbose_name='渠道类型')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('send_resolved', models.BooleanField(default=True, verbose_name='发送恢复通知')),
                ('timeout_seconds', models.PositiveIntegerField(default=8, verbose_name='超时时间')),
                ('config', models.JSONField(blank=True, default=dict, verbose_name='渠道配置')),
                ('template_title', models.CharField(blank=True, default='', max_length=255, verbose_name='标题模板')),
                ('template_body', models.TextField(blank=True, default='', verbose_name='内容模板')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '告警通知渠道',
                'verbose_name_plural': '告警通知渠道',
                'ordering': ['channel_type', 'name'],
            },
        ),
        migrations.CreateModel(
            name='AlertNotificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(default='fire', max_length=32, verbose_name='通知动作')),
                ('status', models.CharField(choices=[('success', '成功'), ('skipped', '跳过'), ('error', '失败')], default='success', max_length=16, verbose_name='状态')),
                ('recipient_summary', models.CharField(blank=True, default='', max_length=255, verbose_name='接收人')),
                ('request_payload', models.JSONField(blank=True, default=dict, verbose_name='请求载荷')),
                ('response_body', models.TextField(blank=True, default='', verbose_name='响应内容')),
                ('error_message', models.TextField(blank=True, default='', verbose_name='错误信息')),
                ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='发送时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
            ],
            options={
                'verbose_name': '告警通知记录',
                'verbose_name_plural': '告警通知记录',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AlertNotificationRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='通知规则名称')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('matchers', models.JSONField(blank=True, default=list, verbose_name='匹配条件')),
                ('min_level', models.CharField(blank=True, choices=[('critical', '严重'), ('warning', '警告'), ('info', '信息')], default='', max_length=16, verbose_name='最低级别')),
                ('notify_on_fire', models.BooleanField(default=True, verbose_name='触发时通知')),
                ('notify_on_resolved', models.BooleanField(default=True, verbose_name='恢复时通知')),
                ('notify_on_escalation', models.BooleanField(default=True, verbose_name='升级时通知')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='说明')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '告警通知规则',
                'verbose_name_plural': '告警通知规则',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='AlertRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64, verbose_name='姓名')),
                ('phone', models.CharField(blank=True, default='', max_length=32, verbose_name='手机号')),
                ('email', models.EmailField(blank=True, default='', max_length=254, verbose_name='邮箱')),
                ('dingtalk_user_id', models.CharField(blank=True, default='', max_length=128, verbose_name='钉钉用户 ID')),
                ('feishu_user_id', models.CharField(blank=True, default='', max_length=128, verbose_name='飞书用户 ID')),
                ('wecom_user_id', models.CharField(blank=True, default='', max_length=128, verbose_name='企微用户 ID')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='说明')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '告警接收人',
                'verbose_name_plural': '告警接收人',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='AlertRecipientGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, unique=True, verbose_name='接收组名称')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='说明')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '告警接收组',
                'verbose_name_plural': '告警接收组',
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='alert',
            name='acknowledged_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='确认时间'),
        ),
        migrations.AddField(
            model_name='alert',
            name='acknowledged_by',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='确认人'),
        ),
        migrations.AddField(
            model_name='alert',
            name='annotations',
            field=models.JSONField(blank=True, default=dict, verbose_name='注解'),
        ),
        migrations.AddField(
            model_name='alert',
            name='business_line',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='业务线'),
        ),
        migrations.AddField(
            model_name='alert',
            name='claimed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='认领时间'),
        ),
        migrations.AddField(
            model_name='alert',
            name='claimed_by',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='认领人'),
        ),
        migrations.AddField(
            model_name='alert',
            name='closed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='关闭时间'),
        ),
        migrations.AddField(
            model_name='alert',
            name='cluster',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='集群'),
        ),
        migrations.AddField(
            model_name='alert',
            name='ends_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='恢复时间'),
        ),
        migrations.AddField(
            model_name='alert',
            name='environment',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='环境'),
        ),
        migrations.AddField(
            model_name='alert',
            name='escalated_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='升级时间'),
        ),
        migrations.AddField(
            model_name='alert',
            name='escalation_level',
            field=models.PositiveIntegerField(default=0, verbose_name='升级级别'),
        ),
        migrations.AddField(
            model_name='alert',
            name='external_id',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='外部事件 ID'),
        ),
        migrations.AddField(
            model_name='alert',
            name='fingerprint',
            field=models.CharField(blank=True, db_index=True, default='', max_length=128, verbose_name='指纹'),
        ),
        migrations.AddField(
            model_name='alert',
            name='group_key',
            field=models.CharField(blank=True, db_index=True, default='', max_length=256, verbose_name='聚合键'),
        ),
        migrations.AddField(
            model_name='alert',
            name='is_suppressed',
            field=models.BooleanField(default=False, verbose_name='已被抑制'),
        ),
        migrations.AddField(
            model_name='alert',
            name='labels',
            field=models.JSONField(blank=True, default=dict, verbose_name='标签'),
        ),
        migrations.AddField(
            model_name='alert',
            name='last_received_at',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='最近接收时间'),
        ),
        migrations.AddField(
            model_name='alert',
            name='metric_name',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='指标名'),
        ),
        migrations.AddField(
            model_name='alert',
            name='mute_until',
            field=models.DateTimeField(blank=True, null=True, verbose_name='屏蔽截止时间'),
        ),
        migrations.AddField(
            model_name='alert',
            name='muted_by',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='屏蔽人'),
        ),
        migrations.AddField(
            model_name='alert',
            name='muted_reason',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='屏蔽原因'),
        ),
        migrations.AddField(
            model_name='alert',
            name='namespace',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='命名空间'),
        ),
        migrations.AddField(
            model_name='alert',
            name='occurrence_count',
            field=models.PositiveIntegerField(default=1, verbose_name='出现次数'),
        ),
        migrations.AddField(
            model_name='alert',
            name='raw_payload',
            field=models.JSONField(blank=True, default=dict, verbose_name='原始载荷'),
        ),
        migrations.AddField(
            model_name='alert',
            name='region',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='地域'),
        ),
        migrations.AddField(
            model_name='alert',
            name='resource',
            field=models.CharField(blank=True, default='', max_length=256, verbose_name='资源标识'),
        ),
        migrations.AddField(
            model_name='alert',
            name='resource_type',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='资源类型'),
        ),
        migrations.AddField(
            model_name='alert',
            name='runbook_url',
            field=models.URLField(blank=True, default='', max_length=500, verbose_name='Runbook'),
        ),
        migrations.AddField(
            model_name='alert',
            name='service',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='服务'),
        ),
        migrations.AddField(
            model_name='alert',
            name='source_type',
            field=models.CharField(choices=[('prometheus', 'Prometheus Alertmanager'), ('zabbix', 'Zabbix'), ('nightingale', '夜莺'), ('aliyun', '阿里云监控'), ('generic', '通用 Webhook')], default='generic', max_length=32, verbose_name='来源类型'),
        ),
        migrations.AddField(
            model_name='alert',
            name='starts_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='触发时间'),
        ),
        migrations.AddField(
            model_name='alert',
            name='status',
            field=models.CharField(choices=[('active', '活跃'), ('resolved', '已恢复'), ('closed', '已关闭'), ('muted', '已屏蔽')], default='active', max_length=16, verbose_name='状态'),
        ),
        migrations.AddField(
            model_name='alert',
            name='suppressed_by',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='抑制来源'),
        ),
        migrations.AddField(
            model_name='alert',
            name='suppressed_until',
            field=models.DateTimeField(blank=True, null=True, verbose_name='抑制截止时间'),
        ),
        migrations.AddField(
            model_name='alert',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='更新时间'),
        ),
        migrations.AddField(
            model_name='alertaction',
            name='alert',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='actions', to='ops.alert', verbose_name='告警'),
        ),
        migrations.AddField(
            model_name='alert',
            name='integration',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='alerts', to='ops.alertintegration', verbose_name='接入源'),
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['status', 'level'], name='ops_alert_status_6220bd_idx'),
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['source_type', 'source'], name='ops_alert_source__f2009d_idx'),
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['service', 'environment'], name='ops_alert_service_5284b8_idx'),
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['cluster', 'namespace'], name='ops_alert_cluster_a76014_idx'),
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['resource_type', 'resource'], name='ops_alert_resourc_30af48_idx'),
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['is_acknowledged', 'created_at'], name='ops_alert_is_ackn_a38db8_idx'),
        ),
        migrations.AddField(
            model_name='alertinteractiontoken',
            name='alert',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='interaction_tokens', to='ops.alert', verbose_name='告警'),
        ),
        migrations.AddField(
            model_name='alertnotificationlog',
            name='alert',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notification_logs', to='ops.alert', verbose_name='告警'),
        ),
        migrations.AddField(
            model_name='alertnotificationlog',
            name='channel',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notification_logs', to='ops.alertnotificationchannel', verbose_name='通知渠道'),
        ),
        migrations.AddField(
            model_name='alertnotificationrule',
            name='aggregation_rule',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notification_rules', to='ops.alertaggregationrule', verbose_name='聚合规则'),
        ),
        migrations.AddField(
            model_name='alertnotificationrule',
            name='channels',
            field=models.ManyToManyField(blank=True, related_name='notification_rules', to='ops.alertnotificationchannel', verbose_name='通知渠道'),
        ),
        migrations.AddField(
            model_name='alertnotificationrule',
            name='escalation_policy',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notification_rules', to='ops.alertescalationpolicy', verbose_name='升级策略'),
        ),
        migrations.AddField(
            model_name='alertnotificationlog',
            name='rule',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notification_logs', to='ops.alertnotificationrule', verbose_name='通知规则'),
        ),
        migrations.AddField(
            model_name='alertrecipient',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='alert_recipients', to=settings.AUTH_USER_MODEL, verbose_name='平台用户'),
        ),
        migrations.AddField(
            model_name='alertnotificationrule',
            name='recipients',
            field=models.ManyToManyField(blank=True, related_name='notification_rules', to='ops.alertrecipient', verbose_name='接收人'),
        ),
        migrations.AddField(
            model_name='alertrecipientgroup',
            name='recipients',
            field=models.ManyToManyField(blank=True, related_name='groups', to='ops.alertrecipient', verbose_name='接收人'),
        ),
        migrations.AddField(
            model_name='alertrecipientgroup',
            name='users',
            field=models.ManyToManyField(blank=True, related_name='alert_recipient_groups', to=settings.AUTH_USER_MODEL, verbose_name='平台用户'),
        ),
        migrations.AddField(
            model_name='alertnotificationrule',
            name='recipient_groups',
            field=models.ManyToManyField(blank=True, related_name='notification_rules', to='ops.alertrecipientgroup', verbose_name='接收组'),
        ),
    ]
