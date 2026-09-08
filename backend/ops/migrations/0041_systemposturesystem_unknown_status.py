from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0040_systemposture_permissions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='systemposturesystem',
            name='base_status',
            field=models.CharField(
                choices=[
                    ('unknown', '未知'),
                    ('healthy', '健康'),
                    ('warning', '告警'),
                    ('critical', '故障'),
                    ('offline', '离线'),
                ],
                default='unknown',
                max_length=16,
                verbose_name='基础状态',
            ),
        ),
    ]
