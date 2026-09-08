from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0032_force_tracing_datasource_live'),
    ]

    operations = [
        migrations.CreateModel(
            name='FireMapSystem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, unique=True, verbose_name='业务系统名称')),
                ('domain', models.CharField(blank=True, default='', max_length=64, verbose_name='业务域')),
                ('tier', models.CharField(blank=True, default='', max_length=64, verbose_name='分层')),
                ('owner', models.CharField(blank=True, default='', max_length=64, verbose_name='负责人')),
                ('summary', models.CharField(blank=True, default='', max_length=255, verbose_name='摘要')),
                ('base_status', models.CharField(choices=[('healthy', '健康'), ('warning', '告警'), ('critical', '故障'), ('offline', '离线')], default='healthy', max_length=16, verbose_name='基础状态')),
                ('health_score', models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='健康分')),
                ('keywords', models.JSONField(blank=True, default=list, verbose_name='匹配关键字')),
                ('north_star', models.JSONField(blank=True, default=dict, verbose_name='核心指标')),
                ('metrics', models.JSONField(blank=True, default=list, verbose_name='核心指标')),
                ('service_specs', models.JSONField(blank=True, default=list, verbose_name='服务分解')),
                ('dependencies', models.JSONField(blank=True, default=list, verbose_name='依赖关系')),
                ('rule_config', models.JSONField(blank=True, default=dict, verbose_name='灭火图规则配置')),
                ('playbook', models.JSONField(blank=True, default=list, verbose_name='处置步骤')),
                ('focus_service_id', models.CharField(blank=True, default='', max_length=128, verbose_name='默认服务节点')),
                ('focus_interface_id', models.CharField(blank=True, default='', max_length=128, verbose_name='默认接口节点')),
                ('focus_keyword', models.CharField(blank=True, default='', max_length=128, verbose_name='默认排障关键字')),
                ('sort_order', models.PositiveIntegerField(default=100, verbose_name='排序')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('created_by', models.CharField(blank=True, default='system', max_length=64, verbose_name='创建人')),
                ('updated_by', models.CharField(blank=True, default='', max_length=64, verbose_name='更新人')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '灭火图业务系统',
                'verbose_name_plural': '灭火图业务系统',
                'ordering': ['sort_order', 'name', '-id'],
            },
        ),
    ]
