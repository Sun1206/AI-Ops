from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


def backfill_deployment_docker_hosts(apps, schema_editor):
    Deployment = apps.get_model('ops', 'Deployment')
    DockerHost = apps.get_model('ops', 'DockerHost')

    status_map = {
        'online': 'connected',
        'offline': 'disconnected',
        'warning': 'error',
    }

    for deployment in Deployment.objects.select_related('host').filter(deploy_mode='docker_compose', docker_host__isnull=True):
        host = deployment.host
        if not host:
            continue
        docker_host = DockerHost.objects.filter(ip_address=host.ip_address).order_by('id').first()
        if not docker_host:
            docker_host = DockerHost.objects.filter(name=host.hostname).order_by('id').first()
        if not docker_host:
            docker_host = DockerHost.objects.create(
                name=host.hostname,
                ip_address=host.ip_address,
                ssh_port=host.ssh_port or 22,
                ssh_user=host.ssh_user or 'root',
                ssh_password=host.ssh_password or '',
                docker_api_version='',
                status=status_map.get(host.status, 'disconnected'),
                description='由应用发布历史主机目标自动迁移',
            )
        deployment.docker_host_id = docker_host.id
        deployment.save(update_fields=['docker_host'])


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0016_remove_deployment_uniq_ops_current_app_env_host_compose_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='deployment',
            name='docker_host',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deployments', to='ops.dockerhost', verbose_name='Docker 环境'),
        ),
        migrations.RunPython(backfill_deployment_docker_hosts, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='deployment',
            name='uniq_ops_curr_biz_app_host',
        ),
        migrations.AddConstraint(
            model_name='deployment',
            constraint=models.UniqueConstraint(condition=Q(('deploy_mode', 'docker_compose'), ('is_current', True)), fields=('business_line', 'app_name', 'environment', 'docker_host'), name='uniq_ops_curr_biz_app_docker_host'),
        ),
    ]
