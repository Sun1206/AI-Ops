from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0055_metricdatasource'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hosttaskexecution',
            name='status',
            field=models.CharField(
                choices=[
                    ('running', '执行中'),
                    ('success', '成功'),
                    ('failed', '失败'),
                    ('skipped', '跳过'),
                ],
                default='success',
                max_length=16,
                verbose_name='执行状态',
            ),
        ),
    ]
