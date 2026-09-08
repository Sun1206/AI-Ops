from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='TerraformStack',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64, verbose_name='方案名称')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='方案描述')),
                ('cloud_provider', models.CharField(choices=[('aliyun', '阿里云'), ('huaweicloud', '华为云')], max_length=32, verbose_name='云厂商')),
                ('region', models.CharField(max_length=64, verbose_name='区域')),
                ('zone', models.CharField(max_length=64, verbose_name='可用区')),
                ('config', models.JSONField(default=dict, verbose_name='基础设施配置')),
                ('summary', models.JSONField(blank=True, default=dict, verbose_name='生成摘要')),
                ('generated_files', models.JSONField(blank=True, default=dict, verbose_name='Terraform 文件')),
                ('created_by', models.CharField(default='', max_length=64, verbose_name='创建人')),
                ('updated_by', models.CharField(default='', max_length=64, verbose_name='更新人')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': 'Terraform 方案',
                'verbose_name_plural': 'Terraform 方案',
                'ordering': ['-updated_at', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='terraformstack',
            constraint=models.UniqueConstraint(fields=('cloud_provider', 'name'), name='iac_terraformstack_provider_name_unique'),
        ),
    ]
