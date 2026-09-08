from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('multicloud', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cloudenvironment',
            name='business_line',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='系统'),
        ),
    ]
