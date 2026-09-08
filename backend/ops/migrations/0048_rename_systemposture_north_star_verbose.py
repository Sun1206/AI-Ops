from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0047_rename_business_line_verbose_to_system'),
    ]

    operations = [
        migrations.AlterField(
            model_name='systemposturesystem',
            name='north_star',
            field=models.JSONField(blank=True, default=dict, verbose_name='核心指标'),
        ),
    ]
