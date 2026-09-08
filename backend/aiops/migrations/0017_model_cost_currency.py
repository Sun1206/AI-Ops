from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aiops', '0016_aiopsexternaltask_agent_results_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiopsmodelprovider',
            name='price_currency',
            field=models.CharField(choices=[('USD', 'USD'), ('CNY', 'CNY')], default='USD', max_length=3, verbose_name='计费币种'),
        ),
        migrations.AddField(
            model_name='aiopsmodelinvocation',
            name='estimated_cost_currency',
            field=models.CharField(choices=[('USD', 'USD'), ('CNY', 'CNY')], default='USD', max_length=3, verbose_name='预估费用币种'),
        ),
    ]
