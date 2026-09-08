from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aiops', '0017_model_cost_currency'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiopsmodelprovider',
            name='provider_preset',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='供应商预设'),
        ),
        migrations.AlterField(
            model_name='aiopsmodelprovider',
            name='max_tokens',
            field=models.PositiveIntegerField(default=10000, verbose_name='最大 Tokens'),
        ),
    ]