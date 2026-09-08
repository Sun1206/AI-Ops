from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aiops', '0005_aiopsknowledgeenvironment'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiopsknowledgeenvironment',
            name='docker_host_ids',
            field=models.JSONField(blank=True, default=list, verbose_name='Docker 环境'),
        ),
        migrations.AddField(
            model_name='aiopsknowledgeenvironment',
            name='k8s_cluster_ids',
            field=models.JSONField(blank=True, default=list, verbose_name='K8s 集群'),
        ),
    ]
