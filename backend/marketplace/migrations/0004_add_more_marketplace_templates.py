from django.db import migrations

from marketplace.template_catalog import TEMPLATES
from marketplace.template_presets import K8S_MANIFESTS


NEW_TEMPLATE_NAMES = {'MongoDB', 'Java', 'Python', 'Go', 'Node.js'}


def add_more_marketplace_templates(apps, schema_editor):
    ServiceTemplate = apps.get_model('marketplace', 'ServiceTemplate')

    for tpl_data in TEMPLATES:
        if tpl_data['name'] not in NEW_TEMPLATE_NAMES:
            continue

        defaults = dict(tpl_data)
        defaults['k8s_manifest_template'] = K8S_MANIFESTS.get(tpl_data['name'], '')
        ServiceTemplate.objects.update_or_create(
            name=tpl_data['name'],
            defaults=defaults,
        )


def remove_more_marketplace_templates(apps, schema_editor):
    ServiceTemplate = apps.get_model('marketplace', 'ServiceTemplate')
    ServiceTemplate.objects.filter(name__in=NEW_TEMPLATE_NAMES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0003_backfill_k8s_templates_and_deployments'),
    ]

    operations = [
        migrations.RunPython(add_more_marketplace_templates, remove_more_marketplace_templates),
    ]
