from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0044_hosttask_task_center_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='hosttask',
            name='target_type',
            field=models.CharField(choices=[('host', '主机资源'), ('k8s', 'K8s 资源')], default='host', max_length=16, verbose_name='目标类型'),
        ),
        migrations.AddField(
            model_name='hosttasktemplate',
            name='target_type',
            field=models.CharField(choices=[('host', '主机资源'), ('k8s', 'K8s 资源')], default='host', max_length=16, verbose_name='目标类型'),
        ),
        migrations.AlterField(
            model_name='hosttask',
            name='execution_mode',
            field=models.CharField(choices=[('ssh', 'SSH'), ('ansible', 'Ansible'), ('k8s_api', 'K8s API')], default='ssh', max_length=16, verbose_name='执行方式'),
        ),
        migrations.AlterField(
            model_name='hosttask',
            name='task_type',
            field=models.CharField(choices=[('check_connection', 'SSH 连通性检查'), ('refresh_metrics', '主机指标刷新'), ('run_command', '批量命令执行'), ('run_playbook', 'Ansible Playbook 执行'), ('service_status', '服务状态巡检'), ('k8s_restart_pod', 'K8s Pod 重启'), ('k8s_pod_exec', 'K8s Pod 命令执行'), ('k8s_scale_workload', 'K8s 工作负载伸缩')], max_length=32, verbose_name='任务类型'),
        ),
        migrations.AlterField(
            model_name='hosttasktemplate',
            name='execution_mode',
            field=models.CharField(choices=[('ssh', 'SSH'), ('ansible', 'Ansible'), ('k8s_api', 'K8s API')], default='ssh', max_length=16, verbose_name='执行方式'),
        ),
        migrations.AlterField(
            model_name='hosttasktemplate',
            name='task_type',
            field=models.CharField(choices=[('check_connection', 'SSH 连通性检查'), ('refresh_metrics', '主机指标刷新'), ('run_command', '批量命令执行'), ('run_playbook', 'Ansible Playbook 执行'), ('service_status', '服务状态巡检'), ('k8s_restart_pod', 'K8s Pod 重启'), ('k8s_pod_exec', 'K8s Pod 命令执行'), ('k8s_scale_workload', 'K8s 工作负载伸缩')], max_length=32, verbose_name='任务类型'),
        ),
        migrations.AddField(
            model_name='hosttaskexecution',
            name='target_id',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='目标 ID'),
        ),
        migrations.AddField(
            model_name='hosttaskexecution',
            name='target_kind',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='目标类型标识'),
        ),
        migrations.AddField(
            model_name='hosttaskexecution',
            name='target_name',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='目标名称'),
        ),
        migrations.AddField(
            model_name='hosttaskexecution',
            name='target_namespace',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='目标命名空间'),
        ),
        migrations.AddField(
            model_name='hosttaskexecution',
            name='target_type',
            field=models.CharField(choices=[('host', '主机资源'), ('k8s', 'K8s 资源')], default='host', max_length=16, verbose_name='目标类型'),
        ),
        migrations.AlterField(
            model_name='hosttaskexecution',
            name='host_ip',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='主机 IP'),
        ),
    ]
