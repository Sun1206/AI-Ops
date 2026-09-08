from django.db import migrations, models
import django.db.models.deletion


DEFAULT_TRACE_ID_FIELDS = ['trace_id', 'traceId', 'traceID']
DEFAULT_TRACE_ID_REGEX = r'"trace_id"\s*:\s*"([0-9a-fA-F]{16,32})"'
DEFAULT_LOG_QUERY_TEMPLATE = '${__tags} | json | trace_id="${__trace.traceId}"'
DEFAULT_LOG_LABEL_MAPPINGS = [
    {'trace_tag': 'service.name', 'log_label': 'container'},
    {'trace_tag': 'service.namespace', 'log_label': 'namespace'},
]


def seed_ecommerce_datasource_link(apps, schema_editor):
    LogDataSource = apps.get_model('ops', 'LogDataSource')
    TracingDataSource = apps.get_model('ops', 'TracingDataSource')
    ObservabilityDataSourceLink = apps.get_model('ops', 'ObservabilityDataSourceLink')

    log_datasource = LogDataSource.objects.filter(name='电商-k3s-loki', provider='loki').first()
    tracing_datasource = TracingDataSource.objects.filter(name='电商-k3s-tempo', provider='tempo').first()
    if not log_datasource or not tracing_datasource:
        return

    ObservabilityDataSourceLink.objects.update_or_create(
        name='电商 k3s Loki ↔ Tempo',
        defaults={
            'log_datasource': log_datasource,
            'tracing_datasource': tracing_datasource,
            'description': '对齐 Grafana 中 Loki derived field 与 Tempo trace-to-logs 的电商 k3s 关联规则。',
            'is_enabled': True,
            'is_default': True,
            'log_to_trace_enabled': True,
            'trace_to_log_enabled': True,
            'trace_id_fields': DEFAULT_TRACE_ID_FIELDS,
            'trace_id_regex': DEFAULT_TRACE_ID_REGEX,
            'log_query_template': DEFAULT_LOG_QUERY_TEMPLATE,
            'log_label_mappings': DEFAULT_LOG_LABEL_MAPPINGS,
            'span_start_shift': '-5m',
            'span_end_shift': '5m',
            'window_minutes': 10,
        },
    )


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0027_grafanasetting_folders'),
    ]

    operations = [
        migrations.CreateModel(
            name='ObservabilityDataSourceLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, unique=True, verbose_name='关联名称')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='描述')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('is_default', models.BooleanField(default=False, verbose_name='默认关联')),
                ('log_to_trace_enabled', models.BooleanField(default=True, verbose_name='日志跳链路')),
                ('trace_to_log_enabled', models.BooleanField(default=True, verbose_name='链路跳日志')),
                ('trace_id_fields', models.JSONField(blank=True, default=list, verbose_name='Trace ID 字段')),
                ('trace_id_regex', models.CharField(blank=True, default='', max_length=255, verbose_name='Trace ID 正则')),
                ('log_query_template', models.TextField(blank=True, default='', verbose_name='日志查询模板')),
                ('log_label_mappings', models.JSONField(blank=True, default=list, verbose_name='日志标签映射')),
                ('span_start_shift', models.CharField(blank=True, default='-5m', max_length=16, verbose_name='Span 开始偏移')),
                ('span_end_shift', models.CharField(blank=True, default='5m', max_length=16, verbose_name='Span 结束偏移')),
                ('window_minutes', models.PositiveIntegerField(default=10, verbose_name='默认查询窗口分钟')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('log_datasource', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='trace_links', to='ops.logdatasource', verbose_name='日志数据源')),
                ('tracing_datasource', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='log_links', to='ops.tracingdatasource', verbose_name='链路数据源')),
            ],
            options={
                'verbose_name': '可观测数据源关联',
                'verbose_name_plural': '可观测数据源关联',
                'ordering': ['-is_default', 'name'],
                'unique_together': {('log_datasource', 'tracing_datasource')},
            },
        ),
        migrations.RunPython(seed_ecommerce_datasource_link, noop),
    ]
