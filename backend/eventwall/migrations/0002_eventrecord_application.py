from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eventwall', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventrecord',
            name='application',
            field=models.CharField(blank=True, db_index=True, default='', max_length=128, verbose_name='Application'),
        ),
    ]
