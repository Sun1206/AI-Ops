from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sqlaudit', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='datasource',
            name='db_type',
            field=models.CharField(
                choices=[('mysql', 'MySQL'), ('mongodb', 'MongoDB'), ('polardb', 'PolarDB')],
                default='mysql',
                max_length=16,
                verbose_name='数据库类型',
            ),
        ),
    ]
