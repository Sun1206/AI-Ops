from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0042_systemposturesystem_warning_risk_label'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemPostureSLAHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.DateField(verbose_name='统计日期')),
                ('system_key', models.CharField(max_length=128, verbose_name='系统标识')),
                ('system_name', models.CharField(max_length=128, verbose_name='系统名称')),
                ('environment', models.CharField(blank=True, default='prod', max_length=32, verbose_name='环境')),
                ('domain', models.CharField(blank=True, default='', max_length=64, verbose_name='业务域')),
                ('status', models.CharField(choices=[('unknown', '未知'), ('healthy', '健康'), ('warning', '风险'), ('critical', '故障')], default='unknown', max_length=16, verbose_name='状态')),
                ('sla_value', models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name='SLA')),
                ('sla_target', models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name='SLA 目标')),
                ('health_score', models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)], verbose_name='健康分')),
                ('metric_label', models.CharField(blank=True, default='SLA', max_length=64, verbose_name='指标名称')),
                ('metric_unit', models.CharField(blank=True, default='%', max_length=16, verbose_name='指标单位')),
                ('snapshot', models.JSONField(blank=True, default=dict, verbose_name='快照')),
                ('captured_at', models.DateTimeField(auto_now=True, verbose_name='采集时间')),
            ],
            options={
                'verbose_name': '系统态势 SLA 历史',
                'verbose_name_plural': '系统态势 SLA 历史',
                'db_table': 'ops_systemposture_sla_history',
                'ordering': ['-day', 'environment', 'system_name'],
            },
        ),
        migrations.AddIndex(
            model_name='systempostureslahistory',
            index=models.Index(fields=['day', 'status'], name='ops_posture_sla_day_status_idx'),
        ),
        migrations.AddIndex(
            model_name='systempostureslahistory',
            index=models.Index(fields=['system_key', '-day'], name='ops_posture_sla_system_day_idx'),
        ),
        migrations.AddConstraint(
            model_name='systempostureslahistory',
            constraint=models.UniqueConstraint(fields=('day', 'system_key'), name='ops_posture_sla_day_system_uniq'),
        ),
    ]
