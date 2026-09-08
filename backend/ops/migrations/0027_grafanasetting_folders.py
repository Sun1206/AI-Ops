from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0026_grafanasetting'),
    ]

    operations = [
        migrations.AddField(
            model_name='grafanasetting',
            name='folders',
            field=models.JSONField(blank=True, default=list, verbose_name='目录配置'),
        ),
    ]
