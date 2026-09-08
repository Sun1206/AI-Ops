from django.db import migrations
from django.utils.text import slugify

from marketplace.template_presets import K8S_MANIFESTS


def backfill_marketplace_k8s_support(apps, schema_editor):
    ServiceTemplate = apps.get_model('marketplace', 'ServiceTemplate')
    ServiceDeployment = apps.get_model('marketplace', 'ServiceDeployment')

    for template in ServiceTemplate.objects.all():
        manifest = K8S_MANIFESTS.get(template.name)
        if manifest:
            template.k8s_manifest_template = manifest
            template.save(update_fields=['k8s_manifest_template'])

    deployments = ServiceDeployment.objects.select_related('template', 'host', 'cluster')
    for deployment in deployments:
        update_fields = []

        if not deployment.deploy_mode:
            deployment.deploy_mode = 'docker_compose'
            update_fields.append('deploy_mode')

        if deployment.deploy_mode == 'docker_compose' and not deployment.release_name:
            deployment.release_name = slugify(deployment.template.name) or f'service-{deployment.template_id}'
            update_fields.append('release_name')

        if deployment.deploy_mode == 'docker_compose' and deployment.namespace:
            deployment.namespace = ''
            update_fields.append('namespace')

        if not deployment.replicas:
            deployment.replicas = 1
            update_fields.append('replicas')

        if update_fields:
            deployment.save(update_fields=update_fields)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0002_alter_servicedeployment_unique_together_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_marketplace_k8s_support, noop_reverse),
    ]
