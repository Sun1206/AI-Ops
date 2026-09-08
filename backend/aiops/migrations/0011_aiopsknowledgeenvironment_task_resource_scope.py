from django.db import migrations, models


def backfill_task_resource_scope(apps, schema_editor):
    knowledge_environment_model = apps.get_model('aiops', 'AIOpsKnowledgeEnvironment')
    resource_group_model = apps.get_model('ops', 'TaskResourceGroup')

    environment_groups = list(resource_group_model.objects.filter(group_type='environment'))
    for config in knowledge_environment_model.objects.all():
        existing_ids = [int(item) for item in (config.task_resource_environment_ids or []) if str(item).isdigit()]
        matched_ids = list(existing_ids)
        candidates = [config.name]
        candidates.extend(config.aliases or [])
        normalized_candidates = [str(item or '').strip().lower() for item in candidates if str(item or '').strip()]
        for group in environment_groups:
            group_names = [group.name, group.code]
            normalized_group_names = [str(item or '').strip().lower() for item in group_names if str(item or '').strip()]
            if not normalized_group_names:
                continue
            matched = False
            for candidate in normalized_candidates:
                if matched:
                    break
                for group_name in normalized_group_names:
                    if candidate == group_name or candidate in group_name or group_name in candidate:
                        matched = True
                        break
            if matched and group.id not in matched_ids:
                matched_ids.append(group.id)
        if matched_ids != existing_ids:
            config.task_resource_environment_ids = matched_ids
            config.save(update_fields=['task_resource_environment_ids'])


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0046_task_resource_base'),
        ('aiops', '0010_aiopsknowledgeenvironment_observability_link_ids'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiopsknowledgeenvironment',
            name='task_resource_environment_ids',
            field=models.JSONField(blank=True, default=list, verbose_name='任务资源底座环境'),
        ),
        migrations.AddField(
            model_name='aiopsknowledgeenvironment',
            name='task_resource_system_ids',
            field=models.JSONField(blank=True, default=list, verbose_name='任务资源底座系统'),
        ),
        migrations.RunPython(backfill_task_resource_scope, migrations.RunPython.noop),
    ]
