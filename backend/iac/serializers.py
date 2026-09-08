from rest_framework import serializers

from .models import TerraformExecution, TerraformResourceBinding, TerraformStack
from .terraform import PROVIDER_CATALOG, build_render_payload, render_terraform_project


class TerraformResourceBindingSerializer(serializers.ModelSerializer):
    cmdb_item_id = serializers.IntegerField(source='cmdb_item.id', read_only=True)
    cmdb_item_name = serializers.CharField(source='cmdb_item.name', read_only=True)
    cmdb_item_status = serializers.CharField(source='cmdb_item.status', read_only=True)
    cmdb_item_type = serializers.CharField(source='cmdb_item.ci_type.name', read_only=True)

    class Meta:
        model = TerraformResourceBinding
        fields = [
            'id',
            'resource_key',
            'resource_name',
            'resource_kind',
            'metadata',
            'cmdb_item_id',
            'cmdb_item_name',
            'cmdb_item_status',
            'cmdb_item_type',
            'created_at',
            'updated_at',
        ]


class TerraformStackListSerializer(serializers.ModelSerializer):
    provider_label = serializers.CharField(source='get_cloud_provider_display', read_only=True)
    generated_file_names = serializers.SerializerMethodField()
    resource_count = serializers.SerializerMethodField()
    binding_count = serializers.SerializerMethodField()

    class Meta:
        model = TerraformStack
        fields = [
            'id',
            'name',
            'description',
            'cloud_provider',
            'provider_label',
            'region',
            'zone',
            'summary',
            'resource_count',
            'binding_count',
            'generated_file_names',
            'workspace_dir',
            'last_execution_status',
            'last_execution_action',
            'last_executed_at',
            'last_cmdb_sync_at',
            'created_by',
            'updated_by',
            'created_at',
            'updated_at',
        ]

    def get_generated_file_names(self, obj):
        return list((obj.generated_files or {}).keys())

    def get_resource_count(self, obj):
        return int((obj.summary or {}).get('resource_count') or 0)

    def get_binding_count(self, obj):
        return obj.resource_bindings.count()


class TerraformStackSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=64, required=False, allow_blank=True)
    region = serializers.CharField(max_length=64, required=False, allow_blank=True)
    zone = serializers.CharField(max_length=64, required=False, allow_blank=True)
    provider_label = serializers.CharField(source='get_cloud_provider_display', read_only=True)
    generated_file_names = serializers.SerializerMethodField()
    resource_count = serializers.SerializerMethodField()
    resource_bindings = TerraformResourceBindingSerializer(many=True, read_only=True)

    class Meta:
        model = TerraformStack
        fields = [
            'id',
            'name',
            'description',
            'cloud_provider',
            'provider_label',
            'region',
            'zone',
            'config',
            'summary',
            'resource_count',
            'generated_files',
            'generated_file_names',
            'workspace_dir',
            'last_execution_status',
            'last_execution_action',
            'last_executed_at',
            'last_cmdb_sync_at',
            'resource_bindings',
            'created_by',
            'updated_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'summary',
            'resource_count',
            'generated_files',
            'generated_file_names',
            'workspace_dir',
            'last_execution_status',
            'last_execution_action',
            'last_executed_at',
            'last_cmdb_sync_at',
            'resource_bindings',
            'created_by',
            'updated_by',
            'created_at',
            'updated_at',
        ]

    def validate_cloud_provider(self, value):
        if value not in PROVIDER_CATALOG:
            raise serializers.ValidationError('暂不支持该云厂商。')
        return value

    def validate(self, attrs):
        payload = build_render_payload(
            name=attrs.get('name', getattr(self.instance, 'name', '')),
            description=attrs.get('description', getattr(self.instance, 'description', '')),
            cloud_provider=attrs.get('cloud_provider', getattr(self.instance, 'cloud_provider', '')),
            region=attrs.get('region', getattr(self.instance, 'region', '')),
            zone=attrs.get('zone', getattr(self.instance, 'zone', '')),
            config=attrs.get('config', getattr(self.instance, 'config', {})),
            secrets=None,
        )
        rendered = render_terraform_project(payload)
        attrs['name'] = payload['name']
        attrs['description'] = payload['description']
        attrs['region'] = payload['region']
        attrs['zone'] = payload['zone']
        attrs['config'] = payload['config']
        attrs['_rendered_summary'] = rendered['summary']
        attrs['_rendered_files'] = rendered['files']
        return attrs

    def get_generated_file_names(self, obj):
        return list((obj.generated_files or {}).keys())

    def get_resource_count(self, obj):
        return int((obj.summary or {}).get('resource_count') or 0)


class TerraformRenderSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64, required=False, allow_blank=True, default='')
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    cloud_provider = serializers.ChoiceField(choices=sorted(PROVIDER_CATALOG.keys()))
    region = serializers.CharField(max_length=64, required=False, allow_blank=True, default='')
    zone = serializers.CharField(max_length=64, required=False, allow_blank=True, default='')
    config = serializers.DictField()
    secrets = serializers.DictField(required=False, default=dict)

    def validate(self, attrs):
        payload = build_render_payload(
            name=attrs['name'],
            description=attrs.get('description', ''),
            cloud_provider=attrs['cloud_provider'],
            region=attrs['region'],
            zone=attrs['zone'],
            config=attrs.get('config', {}),
            secrets=attrs.get('secrets') or {},
        )
        attrs['payload'] = payload
        attrs['rendered'] = render_terraform_project(payload)
        return attrs


class TerraformExecutionSerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source='get_action_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = TerraformExecution
        fields = [
            'id',
            'stack',
            'action',
            'action_label',
            'status',
            'status_label',
            'command',
            'return_code',
            'stdout',
            'stderr',
            'outputs',
            'cmdb_summary',
            'created_by',
            'started_at',
            'finished_at',
            'created_at',
        ]


class TerraformExecutionRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=TerraformExecution.ACTION_CHOICES)
    secrets = serializers.DictField(required=False, default=dict)

    def __init__(self, *args, **kwargs):
        self.stack = kwargs.pop('stack', None)
        super().__init__(*args, **kwargs)

    def validate(self, attrs):
        secrets = attrs.get('secrets') or {}
        action = attrs['action']
        if action != TerraformExecution.ACTION_INIT and not secrets:
            raise serializers.ValidationError({'secrets': '执行 plan/apply/destroy 时需要填写云账号凭证和实例密码。'})
        if self.stack is not None:
            build_render_payload(
                name=self.stack.name,
                description=self.stack.description,
                cloud_provider=self.stack.cloud_provider,
                region=self.stack.region,
                zone=self.stack.zone,
                config=self.stack.config,
                secrets=secrets,
            )
        attrs['secrets'] = secrets
        return attrs
