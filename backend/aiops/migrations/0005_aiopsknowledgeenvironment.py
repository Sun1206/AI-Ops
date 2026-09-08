from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aiops', '0004_aiopschat_mirror_source'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIOpsKnowledgeEnvironment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, unique=True, verbose_name='知识图谱环境名')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='描述')),
                ('event_environments', models.JSONField(blank=True, default=list, verbose_name='事件中心环境')),
                ('grafana_folder_keys', models.JSONField(blank=True, default=list, verbose_name='监控看板目录')),
                ('log_datasource_ids', models.JSONField(blank=True, default=list, verbose_name='日志中心数据源')),
                ('tracing_datasource_ids', models.JSONField(blank=True, default=list, verbose_name='链路追踪数据源')),
                ('alert_environments', models.JSONField(blank=True, default=list, verbose_name='告警中心环境')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('created_by', models.CharField(blank=True, default='', max_length=64, verbose_name='创建人')),
                ('updated_by', models.CharField(blank=True, default='', max_length=64, verbose_name='更新人')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': 'AIOps 知识图谱环境关联',
                'verbose_name_plural': 'AIOps 知识图谱环境关联',
                'ordering': ['name', 'id'],
            },
        ),
    ]
