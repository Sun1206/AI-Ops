from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0046_task_resource_base'),
    ]

    operations = [
        migrations.AlterField(
            model_name='host',
            name='business_line',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='系统'),
        ),
        migrations.AlterField(
            model_name='deployment',
            name='business_line',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='系统'),
        ),
        migrations.AlterField(
            model_name='alert',
            name='business_line',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='系统'),
        ),
        migrations.AlterField(
            model_name='transactionticket',
            name='business_line',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='系统'),
        ),
    ]
