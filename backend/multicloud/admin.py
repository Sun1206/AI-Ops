from django.contrib import admin

from .models import CloudAsset, CloudCredential, CloudEnvironment, CloudSyncTask


@admin.register(CloudCredential)
class CloudCredentialAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'account_id', 'owner', 'is_enabled', 'demo_mode', 'last_test_status', 'last_sync_at')
    list_filter = ('provider', 'is_enabled', 'demo_mode', 'last_test_status')
    search_fields = ('name', 'account_id', 'account_name', 'owner')


@admin.register(CloudEnvironment)
class CloudEnvironmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'credential', 'environment_type', 'region', 'status', 'sync_status', 'last_sync_at')
    list_filter = ('environment_type', 'status', 'sync_status', 'credential__provider')
    search_fields = ('name', 'code', 'business_line', 'owner', 'region')


@admin.register(CloudAsset)
class CloudAssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'resource_type', 'provider', 'environment', 'status', 'risk_level', 'sync_state', 'monthly_cost')
    list_filter = ('provider', 'resource_type', 'status', 'risk_level', 'sync_state')
    search_fields = ('name', 'resource_id', 'private_ip', 'public_ip', 'spec')


@admin.register(CloudSyncTask)
class CloudSyncTaskAdmin(admin.ModelAdmin):
    list_display = ('task_type', 'status', 'credential', 'environment', 'operator', 'started_at', 'finished_at')
    list_filter = ('task_type', 'status')
    search_fields = ('operator', 'summary')
