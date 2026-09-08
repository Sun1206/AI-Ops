from ops.models import (
    GrafanaSetting,
    LogDataSource,
    MetricDataSource,
    ObservabilityDataSourceLink,
    TracingDataSource,
)

from .common import get_or_create_first


METRICS = [
    ('生产 Prometheus', 'prod', 'prod-shanghai', 'prometheus', 'http://prometheus.ops.internal:9090', True),
    ('长期指标存储', 'prod', 'global', 'victoriametrics', 'http://vmselect.ops.internal:8481', False),
    ('预发布 Prometheus', 'staging', 'staging-shanghai', 'prometheus', 'http://prometheus-staging.ops.internal:9090', False),
]

TRACING = [
    ('生产 Tempo', 'tempo', 'http://tempo.ops.internal:3200', True),
    ('预发布 Jaeger', 'jaeger', 'http://jaeger-staging.ops.internal:16686', False),
]


def seed_observability(stats, base):
    staging_log = get_or_create_first(
        LogDataSource,
        {'name': '预发布日志中心'},
        {
            'provider': 'loki',
            'description': '预发布应用与基础设施日志',
            'config': {'base_url': 'http://loki-staging.ops.internal:3100'},
            'is_enabled': False,
            'is_default': False,
        },
        stats,
    )
    log_sources = [base['log_source'], staging_log]

    metrics = []
    for name, environment, cluster_name, tsdb_type, url, is_default in METRICS:
        metrics.append(get_or_create_first(
            MetricDataSource,
            {'name': name},
            {
                'provider': 'prometheus',
                'description': f'{environment} 指标查询入口',
                'environment': environment,
                'cluster_name': cluster_name,
                'tsdb_type': tsdb_type,
                'config': {'base_url': url, 'timeout_seconds': 8},
                'is_enabled': False,
                'is_default': is_default,
            },
            stats,
        ))

    tracings = []
    for name, provider, url, is_default in TRACING:
        tracings.append(get_or_create_first(
            TracingDataSource,
            {'name': name},
            {
                'provider': provider,
                'description': f'{name}链路检索入口',
                'config': {'base_url': url, 'timeout_seconds': 8},
                'is_enabled': False,
                'is_default': is_default,
            },
            stats,
        ))

    links = []
    for log_index, log_source in enumerate(log_sources):
        for tracing_index, tracing in enumerate(tracings):
            link = get_or_create_first(
                ObservabilityDataSourceLink,
                {'log_datasource': log_source, 'tracing_datasource': tracing},
                {
                    'name': f'{log_source.name}到{tracing.name}',
                    'description': '日志、链路与看板上下文跳转',
                    'is_enabled': False,
                    'is_default': log_index == 0 and tracing_index == 0,
                    'log_to_trace_enabled': True,
                    'trace_to_log_enabled': True,
                    'log_to_grafana_enabled': True,
                    'trace_to_grafana_enabled': True,
                    'grafana_to_log_enabled': True,
                    'grafana_to_trace_enabled': True,
                    'trace_id_fields': ['trace_id', 'traceId', 'trace.id'],
                    'trace_id_regex': '(?i)[0-9a-f]{16,32}',
                    'log_query_template': '{trace_id}',
                    'log_label_mappings': [
                        {'source': 'service_name', 'target': 'service'},
                        {'source': 'environment', 'target': 'environment'},
                    ],
                    'grafana_dashboard_key': 'service-overview',
                    'grafana_variable_mappings': [
                        {'source': 'service_name', 'target': 'service'},
                        {'source': 'environment', 'target': 'env'},
                    ],
                    'span_start_shift': '-5m',
                    'span_end_shift': '5m',
                    'window_minutes': 10,
                },
                stats,
            )
            links.append(link)

    grafana = get_or_create_first(
        GrafanaSetting,
        {'name': 'default'},
        {
            'enabled': False,
            'url': 'http://grafana.ops.internal:3000',
            'default_path': '/d/service-overview',
            'folders': [
                {'key': 'applications', 'name': '应用监控'},
                {'key': 'infrastructure', 'name': '基础设施'},
            ],
            'dashboards': [
                {
                    'key': 'service-overview',
                    'name': '服务总览',
                    'path': '/d/service-overview',
                    'folder_key': 'applications',
                },
                {
                    'key': 'k8s-cluster',
                    'name': 'Kubernetes 集群',
                    'path': '/d/k8s-cluster',
                    'folder_key': 'infrastructure',
                },
                {
                    'key': 'database-health',
                    'name': '数据库健康度',
                    'path': '/d/database-health',
                    'folder_key': 'infrastructure',
                },
            ],
            'updated_by': 'ops.reader',
        },
        stats,
    )
    return {
        'log_sources': log_sources,
        'metrics': metrics,
        'tracings': tracings,
        'links': links,
        'grafana': grafana,
    }
