from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('aiops', '0011_aiopsknowledgeenvironment_task_resource_scope'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='aiopsknowledgeenvironment',
            name='task_resource_system_ids',
        ),
    ]
