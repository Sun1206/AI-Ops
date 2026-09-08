from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0037_systemposturesystem_environment'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameModel(
                    old_name='FireMapSystem',
                    new_name='SystemPostureSystem',
                ),
                migrations.AlterModelOptions(
                    name='systemposturesystem',
                    options={
                        'ordering': ['sort_order', 'name', '-id'],
                        'verbose_name': '系统态势业务系统',
                        'verbose_name_plural': '系统态势业务系统',
                    },
                ),
                migrations.AlterModelTable(
                    name='systemposturesystem',
                    table='ops_firemapsystem',
                ),
                migrations.AlterField(
                    model_name='systemposturesystem',
                    name='rule_config',
                    field=models.JSONField(blank=True, default=dict, verbose_name='系统态势规则配置'),
                ),
            ],
        ),
        migrations.CreateModel(
            name='SystemPostureEnvironment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=64, unique=True, verbose_name='环境标识')),
                ('name', models.CharField(max_length=64, verbose_name='环境名称')),
                ('sort_order', models.PositiveIntegerField(default=100, verbose_name='排序')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('created_by', models.CharField(blank=True, default='system', max_length=64, verbose_name='创建人')),
                ('updated_by', models.CharField(blank=True, default='', max_length=64, verbose_name='更新人')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'db_table': 'ops_systempostureenvironment',
                'verbose_name': '系统态势环境',
                'verbose_name_plural': '系统态势环境',
                'ordering': ['sort_order', 'id'],
            },
        ),
    ]
