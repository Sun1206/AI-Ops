from decimal import Decimal

from rest_framework import serializers

from .models import CloudAsset, CloudCredential, CloudEnvironment, CloudSyncTask
from .services import PROVIDER_CATALOG


class CloudCredentialSerializer(serializers.ModelSerializer):
    provider_label = serializers.CharField(source='get_provider_display', read_only=True)
    auth_mode_label = serializers.CharField(source='get_auth_mode_display', read_only=True)
    environment_count = serializers.SerializerMethodField()
    asset_count = serializers.SerializerMethodField()
    masked_secret = serializers.SerializerMethodField()

    class Meta:
        model = CloudCredential
        fields = [
            'id', 'provider', 'provider_label', 'name', 'account_id', 'account_name', 'auth_mode', 'auth_mode_label',
            'access_key_id', 'access_key_secret', 'masked_secret', 'project_id', 'role_arn', 'external_id',
            'default_region', 'owner', 'description', 'tags', 'is_enabled', 'demo_mode', 'last_test_status',
            'last_test_message', 'last_sync_at', 'environment_count', 'asset_count', 'created_by', 'updated_by',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['last_test_status', 'last_test_message', 'last_sync_at', 'environment_count', 'asset_count', 'created_by', 'updated_by', 'created_at', 'updated_at']
        extra_kwargs = {'access_key_secret': {'write_only': True, 'required': False, 'allow_blank': True}}

    def validate_provider(self, value):
        if value not in PROVIDER_CATALOG:
            raise serializers.ValidationError('暂不支持该云厂商。')
        return value

    def validate(self, attrs):
        if self.instance and attrs.get('access_key_secret', None) == '':
            attrs.pop('access_key_secret')
        return attrs

    def get_environment_count(self, obj):
        return obj.environments.count()

    def get_asset_count(self, obj):
        return CloudAsset.objects.filter(environment__credential=obj).count()

    def get_masked_secret(self, obj):
        if not obj.access_key_secret:
            return ''
        if obj.demo_mode:
            return obj.access_key_secret
        return f'{obj.access_key_secret[:2]}******{obj.access_key_secret[-2:]}'


class CloudEnvironmentSerializer(serializers.ModelSerializer):
    credential_name = serializers.CharField(source='credential.name', read_only=True)
    provider = serializers.CharField(source='credential.provider', read_only=True)
    provider_label = serializers.CharField(source='credential.get_provider_display', read_only=True)
    environment_type_label = serializers.CharField(source='get_environment_type_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    sync_status_label = serializers.CharField(source='get_sync_status_display', read_only=True)
    asset_count = serializers.SerializerMethodField()
    monthly_cost = serializers.SerializerMethodField()
    risk_count = serializers.SerializerMethodField()

    class Meta:
        model = CloudEnvironment
        fields = [
            'id', 'credential', 'credential_name', 'provider', 'provider_label', 'name', 'code', 'business_line',
            'environment_type', 'environment_type_label', 'region', 'zone', 'vpc_name', 'network_cidr', 'owner',
            'status', 'status_label', 'sync_status', 'sync_status_label', 'description', 'tags', 'summary',
            'asset_count', 'monthly_cost', 'risk_count', 'last_sync_at', 'last_cmdb_sync_at', 'created_by',
            'updated_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['credential_name', 'provider', 'provider_label', 'summary', 'asset_count', 'monthly_cost', 'risk_count', 'last_sync_at', 'last_cmdb_sync_at', 'created_by', 'updated_by', 'created_at', 'updated_at']

    def get_asset_count(self, obj):
        return obj.assets.count()

    def get_monthly_cost(self, obj):
        return float(sum((asset.monthly_cost or Decimal('0')) for asset in obj.assets.all()))

    def get_risk_count(self, obj):
        return obj.assets.filter(risk_level__in=['warning', 'critical']).count()


class CloudAssetSerializer(serializers.ModelSerializer):
    provider_label = serializers.CharField(source='get_provider_display', read_only=True)
    resource_type_label = serializers.CharField(source='get_resource_type_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    risk_level_label = serializers.CharField(source='get_risk_level_display', read_only=True)
    sync_state_label = serializers.CharField(source='get_sync_state_display', read_only=True)
    environment_name = serializers.CharField(source='environment.name', read_only=True)
    credential_name = serializers.CharField(source='environment.credential.name', read_only=True)

    class Meta:
        model = CloudAsset
        fields = [
            'id', 'environment', 'environment_name', 'credential_name', 'provider', 'provider_label', 'resource_type',
            'resource_type_label', 'resource_id', 'name', 'region', 'zone', 'status', 'status_label', 'charge_type',
            'private_ip', 'public_ip', 'vpc_name', 'spec', 'cpu', 'memory_gb', 'disk_gb', 'monthly_cost',
            'cost_currency', 'risk_level', 'risk_level_label', 'sync_state', 'sync_state_label', 'tags',
            'metadata', 'synced_at', 'created_at', 'updated_at',
        ]


class CloudSyncTaskSerializer(serializers.ModelSerializer):
    task_type_label = serializers.CharField(source='get_task_type_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    credential_name = serializers.CharField(source='credential.name', read_only=True)
    environment_name = serializers.CharField(source='environment.name', read_only=True)
    target_display = serializers.CharField(read_only=True)

    class Meta:
        model = CloudSyncTask
        fields = [
            'id', 'credential', 'credential_name', 'environment', 'environment_name', 'target_display', 'task_type',
            'task_type_label', 'status', 'status_label', 'operator', 'summary', 'result', 'started_at', 'finished_at',
            'created_at',
        ]
