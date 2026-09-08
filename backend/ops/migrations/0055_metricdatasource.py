from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0054_remove_dirty_prod_posture_placeholder'),
    ]

    operations = [
        migrations.CreateModel(
            name='MetricDataSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, unique=True, verbose_name='指标数据源名称')),
                ('provider', models.CharField(choices=[('prometheus', 'Prometheus Like')], default='prometheus', max_length=32, verbose_name='指标数据源类型')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='描述')),
                ('environment', models.CharField(blank=True, default='', max_length=32, verbose_name='环境')),
                ('cluster_name', models.CharField(blank=True, default='', max_length=128, verbose_name='集群标识')),
                ('tsdb_type', models.CharField(blank=True, default='prometheus', max_length=32, verbose_name='TSDB 类型')),
                ('config', models.JSONField(blank=True, default=dict, verbose_name='连接配置')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('is_default', models.BooleanField(default=False, verbose_name='默认数据源')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '指标数据源',
                'verbose_name_plural': '指标数据源',
                'ordering': ['environment', '-is_default', 'name'],
            },
        ),
        migrations.AddIndex(
            model_name='metricdatasource',
            index=models.Index(fields=['environment', 'is_enabled'], name='ops_metric_ds_env_enabled_idx'),
        ),
        migrations.AddIndex(
            model_name='metricdatasource',
            index=models.Index(fields=['provider', 'is_enabled'], name='ops_metric_ds_provider_idx'),
        ),
    ]
