from django.contrib import admin

from .models import TerraformExecution, TerraformResourceBinding, TerraformStack


class TerraformExecutionInline(admin.TabularInline):
    model = TerraformExecution
    extra = 0
    fields = ('action', 'status', 'return_code', 'created_by', 'started_at', 'finished_at')
    readonly_fields = fields
    can_delete = False
    show_change_link = True


class TerraformResourceBindingInline(admin.TabularInline):
    model = TerraformResourceBinding
    extra = 0
    fields = ('resource_key', 'resource_name', 'resource_kind', 'cmdb_item', 'updated_at')
    readonly_fields = fields
    can_delete = False
    show_change_link = True


@admin.register(TerraformStack)
class TerraformStackAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'cloud_provider',
        'region',
        'zone',
        'last_execution_status',
        'last_execution_action',
        'last_executed_at',
        'created_by',
        'updated_by',
        'updated_at',
    )
    search_fields = ('name', 'description', 'cloud_provider', 'region', 'zone', 'created_by', 'updated_by')
    list_filter = ('cloud_provider', 'last_execution_status', 'last_execution_action', 'region')
    readonly_fields = ('summary', 'generated_files', 'workspace_dir', 'last_executed_at', 'last_cmdb_sync_at')
    inlines = [TerraformExecutionInline, TerraformResourceBindingInline]


@admin.register(TerraformExecution)
class TerraformExecutionAdmin(admin.ModelAdmin):
    list_display = ('stack', 'action', 'status', 'return_code', 'created_by', 'started_at', 'finished_at')
    search_fields = ('stack__name', 'action', 'status', 'created_by', 'command')
    list_filter = ('action', 'status', 'created_by')
    readonly_fields = ('stdout', 'stderr', 'outputs', 'cmdb_summary')


@admin.register(TerraformResourceBinding)
class TerraformResourceBindingAdmin(admin.ModelAdmin):
    list_display = ('stack', 'resource_key', 'resource_name', 'resource_kind', 'cmdb_item', 'updated_at')
    search_fields = ('stack__name', 'resource_key', 'resource_name', 'resource_kind', 'cmdb_item__name')
    list_filter = ('resource_kind',)
