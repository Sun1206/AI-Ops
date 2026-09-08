from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aiops', '0008_aiopsknowledgeenvironment_k8s_namespaces'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiopsknowledgeenvironment',
            name='aliases',
            field=models.JSONField(blank=True, default=list, verbose_name='环境别名'),
        ),
        migrations.AddField(
            model_name='aiopsknowledgeenvironment',
            name='posture_environments',
            field=models.JSONField(blank=True, default=list, verbose_name='系统态势环境'),
        ),
        migrations.AddField(
            model_name='aiopschatsession',
            name='context',
            field=models.JSONField(blank=True, default=dict, verbose_name='上下文'),
        ),
    ]
