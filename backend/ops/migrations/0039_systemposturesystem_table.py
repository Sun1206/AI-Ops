from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0038_systempostureenvironment'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='systemposturesystem',
            table='ops_system_posturesystem',
        ),
    ]
