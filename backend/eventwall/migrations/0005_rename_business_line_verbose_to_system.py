from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eventwall', '0004_rename_eventsource_code_verbose_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eventrecord',
            name='business_line',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='系统'),
        ),
    ]
