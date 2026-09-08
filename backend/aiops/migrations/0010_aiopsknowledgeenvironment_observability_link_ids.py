from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aiops', '0009_aiops_context_and_environment_aliases'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiopsknowledgeenvironment',
            name='observability_link_ids',
            field=models.JSONField(blank=True, default=list, verbose_name='可观测性关联配置'),
        ),
    ]
