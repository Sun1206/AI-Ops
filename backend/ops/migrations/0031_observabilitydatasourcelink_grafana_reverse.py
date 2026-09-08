from django.db import migrations, models


WORKLOAD_DASHBOARD = {
    'key': 'kubernetes-compute-resources-workload',
    'slug': 'kubernetes-compute-resources-workload',
    'title': 'Kubernetes / Compute Resources / Workload',
    'description': '按 namespace 和 workload 查看 Kubernetes 工作负载资源。',
    'folder': 'Kubernetes / Compute Resources',
    'path': '/d/k8s-resources-workload',
    'full_url': '',
    'panel_count': 16,
    'tags': ['Kubernetes', 'Workload', 'Compute'],
}

WORKLOAD_VARIABLE_MAPPINGS = [
    {'trace_tag': 'service.name', 'variable': 'workload'},
    {'trace_tag': 'service.namespace', 'variable': 'namespace'},
]


def seed_workload_dashboard_link(apps, schema_editor):
    ObservabilityDataSourceLink = apps.get_model('ops', 'ObservabilityDataSourceLink')
    GrafanaSetting = apps.get_model('ops', 'GrafanaSetting')

    ObservabilityDataSourceLink.objects.filter(name='电商 k3s Loki ↔ Tempo').update(
        grafana_to_log_enabled=True,
        grafana_to_trace_enabled=True,
        grafana_dashboard_key=WORKLOAD_DASHBOARD['key'],
        grafana_variable_mappings=WORKLOAD_VARIABLE_MAPPINGS,
    )

    setting = GrafanaSetting.objects.filter(name='default').first()
    if not setting:
        return
    dashboards = list(setting.dashboards or [])
    if not any(
        item.get('key') == WORKLOAD_DASHBOARD['key'] or item.get('title') == WORKLOAD_DASHBOARD['title']
        for item in dashboards
    ):
        dashboards.append(WORKLOAD_DASHBOARD)
        setting.dashboards = dashboards
        setting.save(update_fields=['dashboards', 'updated_at'])


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0030_observabilitydatasourcelink_log_to_grafana'),
    ]

    operations = [
        migrations.AddField(
            model_name='observabilitydatasourcelink',
            name='grafana_to_log_enabled',
            field=models.BooleanField(default=True, verbose_name='看板跳日志'),
        ),
        migrations.AddField(
            model_name='observabilitydatasourcelink',
            name='grafana_to_trace_enabled',
            field=models.BooleanField(default=True, verbose_name='看板跳链路'),
        ),
        migrations.RunPython(seed_workload_dashboard_link, noop),
    ]
