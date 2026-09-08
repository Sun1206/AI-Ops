from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aiops', '0007_aiopsknowledgeenvironment_snapshots'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiopsknowledgeenvironment',
            name='k8s_namespaces',
            field=models.JSONField(blank=True, default=dict, verbose_name='K8s 命名空间'),
        ),
    ]
