from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rbac', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemModuleSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=64, unique=True, verbose_name='模块编码')),
                ('enabled', models.BooleanField(default=True, verbose_name='是否显示')),
                ('updated_by', models.CharField(blank=True, default='', max_length=150, verbose_name='更新人')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '系统模块配置',
                'verbose_name_plural': '系统模块配置',
                'ordering': ['code'],
            },
        ),
    ]
