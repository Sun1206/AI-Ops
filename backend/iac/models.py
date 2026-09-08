from django.db import models


class TerraformStack(models.Model):
    PROVIDER_ALIYUN = 'aliyun'
    PROVIDER_HUAWEICLOUD = 'huaweicloud'

    PROVIDER_CHOICES = [
        (PROVIDER_ALIYUN, '阿里云'),
        (PROVIDER_HUAWEICLOUD, '华为云'),
    ]

    name = models.CharField('方案名称', max_length=64)
    description = models.CharField('方案描述', max_length=255, blank=True, default='')
    cloud_provider = models.CharField('云厂商', max_length=32, choices=PROVIDER_CHOICES)
    region = models.CharField('区域', max_length=64)
    zone = models.CharField('可用区', max_length=64)
    config = models.JSONField('基础设施配置', default=dict)
    summary = models.JSONField('生成摘要', default=dict, blank=True)
    generated_files = models.JSONField('Terraform 文件', default=dict, blank=True)
    workspace_dir = models.CharField('执行工作目录', max_length=255, blank=True, default='')
    last_execution_status = models.CharField('最近执行状态', max_length=16, blank=True, default='')
    last_execution_action = models.CharField('最近执行动作', max_length=16, blank=True, default='')
    last_executed_at = models.DateTimeField('最近执行时间', null=True, blank=True)
    last_cmdb_sync_at = models.DateTimeField('最近同步 CMDB 时间', null=True, blank=True)
    created_by = models.CharField('创建人', max_length=64, default='')
    updated_by = models.CharField('更新人', max_length=64, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        verbose_name = 'Terraform 方案'
        verbose_name_plural = 'Terraform 方案'
        constraints = [
            models.UniqueConstraint(
                fields=['cloud_provider', 'name'],
                name='iac_terraformstack_provider_name_unique',
            )
        ]

    def __str__(self):
        return f'{self.get_cloud_provider_display()} - {self.name}'


class TerraformExecution(models.Model):
    ACTION_INIT = 'init'
    ACTION_PLAN = 'plan'
    ACTION_APPLY = 'apply'
    ACTION_DESTROY = 'destroy'

    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'

    ACTION_CHOICES = [
        (ACTION_INIT, '初始化'),
        (ACTION_PLAN, '计划'),
        (ACTION_APPLY, '执行'),
        (ACTION_DESTROY, '销毁'),
    ]
    STATUS_CHOICES = [
        (STATUS_PENDING, '待执行'),
        (STATUS_RUNNING, '执行中'),
        (STATUS_SUCCESS, '成功'),
        (STATUS_FAILED, '失败'),
    ]

    stack = models.ForeignKey(TerraformStack, on_delete=models.CASCADE, related_name='executions')
    action = models.CharField('执行动作', max_length=16, choices=ACTION_CHOICES)
    status = models.CharField('执行状态', max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    command = models.CharField('执行命令', max_length=255, blank=True, default='')
    return_code = models.IntegerField('返回码', null=True, blank=True)
    stdout = models.TextField('标准输出', blank=True, default='')
    stderr = models.TextField('标准错误', blank=True, default='')
    outputs = models.JSONField('执行结果', default=dict, blank=True)
    cmdb_summary = models.JSONField('CMDB 同步摘要', default=dict, blank=True)
    created_by = models.CharField('执行人', max_length=64, default='')
    started_at = models.DateTimeField('开始时间', null=True, blank=True)
    finished_at = models.DateTimeField('结束时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Terraform 执行记录'
        verbose_name_plural = 'Terraform 执行记录'

    def __str__(self):
        return f'{self.stack.name} - {self.action} - {self.status}'


class TerraformResourceBinding(models.Model):
    stack = models.ForeignKey(TerraformStack, on_delete=models.CASCADE, related_name='resource_bindings')
    resource_key = models.CharField('资源键', max_length=64)
    resource_name = models.CharField('资源名称', max_length=128)
    resource_kind = models.CharField('资源类型', max_length=64)
    cmdb_item = models.ForeignKey('cmdb.ConfigItem', on_delete=models.CASCADE, related_name='terraform_bindings')
    metadata = models.JSONField('绑定元数据', default=dict, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['resource_key']
        verbose_name = 'Terraform 资源绑定'
        verbose_name_plural = 'Terraform 资源绑定'
        constraints = [
            models.UniqueConstraint(
                fields=['stack', 'resource_key'],
                name='iac_resourcebinding_stack_key_unique',
            )
        ]

    def __str__(self):
        return f'{self.stack.name} - {self.resource_key}'
