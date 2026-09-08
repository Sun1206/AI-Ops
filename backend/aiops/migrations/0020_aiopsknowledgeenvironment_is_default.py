from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aiops', '0019_aiopsknowledgeenvironment_metric_datasource_ids'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiopsknowledgeenvironment',
            name='is_default',
            field=models.BooleanField(default=False, verbose_name='默认图谱'),
        ),
    ]
