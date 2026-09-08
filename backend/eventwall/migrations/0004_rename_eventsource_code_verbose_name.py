from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eventwall', '0003_eventsource_external_source'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eventsource',
            name='code',
            field=models.SlugField(max_length=64, unique=True, verbose_name='接入类型'),
        ),
    ]
