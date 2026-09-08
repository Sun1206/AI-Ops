from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0045_general_task_targets'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskResourceGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80, verbose_name='名称')),
                ('code', models.SlugField(blank=True, default='', max_length=80, verbose_name='编码')),
                ('group_type', models.CharField(choices=[('environment', '环境'), ('system', '系统')], max_length=20, verbose_name='节点类型')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='说明')),
                ('sort_order', models.PositiveIntegerField(default=100, verbose_name='排序')),
                ('created_by', models.CharField(blank=True, default='system', max_length=64, verbose_name='创建人')),
                ('updated_by', models.CharField(blank=True, default='', max_length=64, verbose_name='更新人')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='ops.taskresourcegroup', verbose_name='上级节点')),
            ],
            options={
                'verbose_name': '任务资源分组',
                'verbose_name_plural': '任务资源分组',
                'ordering': ['group_type', 'sort_order', 'name', 'id'],
            },
        ),
        migrations.CreateModel(
            name='TaskResource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='资源名称')),
                ('resource_type', models.CharField(choices=[('host', '主机'), ('k8s', 'K8s')], default='host', max_length=16, verbose_name='资源类型')),
                ('status', models.CharField(choices=[('active', '可用'), ('inactive', '停用'), ('warning', '异常')], default='active', max_length=16, verbose_name='状态')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP 地址')),
                ('ssh_port', models.PositiveIntegerField(default=22, verbose_name='SSH 端口')),
                ('ssh_user', models.CharField(blank=True, default='root', max_length=64, verbose_name='SSH 用户')),
                ('ssh_password', models.CharField(blank=True, default='', max_length=256, verbose_name='SSH 密码')),
                ('namespace', models.CharField(blank=True, default='default', max_length=128, verbose_name='命名空间')),
                ('owner', models.CharField(blank=True, default='', max_length=64, verbose_name='负责人')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='说明')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='扩展信息')),
                ('created_by', models.CharField(blank=True, default='system', max_length=64, verbose_name='创建人')),
                ('updated_by', models.CharField(blank=True, default='', max_length=64, verbose_name='更新人')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('cluster', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_resources', to='ops.k8scluster', verbose_name='K8s 集群')),
                ('environment', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='environment_resources', to='ops.taskresourcegroup', verbose_name='环境')),
                ('system', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='system_resources', to='ops.taskresourcegroup', verbose_name='系统')),
            ],
            options={
                'verbose_name': '任务执行资源',
                'verbose_name_plural': '任务执行资源',
                'ordering': ['environment__sort_order', 'system__sort_order', 'resource_type', 'name', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='taskresourcegroup',
            index=models.Index(fields=['group_type', 'parent', 'sort_order'], name='ops_taskres_group_t_c23ca4_idx'),
        ),
        migrations.AddConstraint(
            model_name='taskresourcegroup',
            constraint=models.UniqueConstraint(fields=('group_type', 'parent', 'name'), name='uniq_ops_task_resource_group_scope_name'),
        ),
        migrations.AddIndex(
            model_name='taskresource',
            index=models.Index(fields=['resource_type', 'status'], name='ops_taskres_resourc_81de26_idx'),
        ),
        migrations.AddIndex(
            model_name='taskresource',
            index=models.Index(fields=['environment', 'system', 'resource_type'], name='ops_taskres_environ_ca6402_idx'),
        ),
    ]
