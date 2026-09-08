from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aiops', '0006_knowledge_environment_infrastructure'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiopsknowledgeenvironment',
            name='association_snapshot',
            field=models.JSONField(blank=True, default=dict, verbose_name='关联快照'),
        ),
        migrations.AddField(
            model_name='aiopsknowledgeenvironment',
            name='child_node_snapshot',
            field=models.JSONField(blank=True, default=dict, verbose_name='子节点快照'),
        ),
        migrations.AddField(
            model_name='aiopsknowledgeenvironment',
            name='snapshot_generated_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='快照生成时间'),
        ),
    ]
