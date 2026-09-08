"""
初始化工具市场内置模板
用法: python manage.py seed_templates
"""

from django.core.management.base import BaseCommand

from marketplace.models import ServiceTemplate
from marketplace.template_catalog import TEMPLATES
from marketplace.template_presets import K8S_MANIFESTS


class Command(BaseCommand):
    help = '初始化工具市场模板数据（17 个模板）'

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for tpl_data in TEMPLATES:
            defaults = dict(tpl_data)
            defaults['k8s_manifest_template'] = K8S_MANIFESTS.get(tpl_data['name'], '')
            _, created = ServiceTemplate.objects.update_or_create(
                name=tpl_data['name'],
                defaults=defaults,
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'完成! 新增 {created_count} 个, 更新 {updated_count} 个模板'
        ))
