from rest_framework import serializers

from .models import ServiceTemplate, ServiceDeployment


class ServiceTemplateSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    available_deploy_modes = serializers.SerializerMethodField()

    def get_available_deploy_modes(self, obj):
        return obj.available_deploy_modes

    class Meta:
        model = ServiceTemplate
        fields = [
            'id', 'name', 'icon', 'category', 'category_display',
            'description', 'versions', 'env_schema', 'is_active', 'sort_order',
            'available_deploy_modes',
        ]


class ServiceDeploymentSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    template_icon = serializers.CharField(source='template.icon', read_only=True)
    host_name = serializers.CharField(source='host.hostname', read_only=True, default='')
    host_ip = serializers.CharField(source='host.ip_address', read_only=True, default='')
    cluster_name = serializers.CharField(source='cluster.name', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    deploy_mode_display = serializers.CharField(source='get_deploy_mode_display', read_only=True)
    target_display = serializers.CharField(read_only=True)

    class Meta:
        model = ServiceDeployment
        fields = [
            'id', 'template', 'template_name', 'template_icon',
            'deploy_mode', 'deploy_mode_display',
            'host', 'host_name', 'host_ip',
            'cluster', 'cluster_name', 'namespace', 'release_name', 'replicas',
            'target_display',
            'version', 'status', 'status_display',
            'env_config', 'deploy_log', 'deployer', 'deploy_dir',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['status', 'deploy_log', 'deploy_dir']


class DeployRequestSerializer(serializers.Serializer):
    """部署请求"""

    template_id = serializers.IntegerField()
    deploy_mode = serializers.ChoiceField(choices=ServiceDeployment.DEPLOY_MODE_CHOICES, default='docker_compose')
    host_id = serializers.IntegerField(required=False, allow_null=True)
    cluster_id = serializers.IntegerField(required=False, allow_null=True)
    namespace = serializers.CharField(max_length=128, required=False, allow_blank=True, default='default')
    release_name = serializers.CharField(max_length=128, required=False, allow_blank=True, default='')
    replicas = serializers.IntegerField(required=False, min_value=1, default=1)
    version = serializers.CharField(max_length=32)
    env_config = serializers.DictField(required=False, default=dict)
    deployer = serializers.CharField(max_length=64, default='admin')

    def validate(self, attrs):
        deploy_mode = attrs.get('deploy_mode')

        if deploy_mode == 'docker_compose':
            if not attrs.get('host_id'):
                raise serializers.ValidationError({'host_id': 'Docker Compose 模式必须选择目标主机'})
            attrs['cluster_id'] = None
            attrs['namespace'] = ''
            attrs['release_name'] = ''
        elif deploy_mode == 'k8s':
            if not attrs.get('cluster_id'):
                raise serializers.ValidationError({'cluster_id': 'K8s 模式必须选择目标集群'})
            attrs['host_id'] = None
            attrs['namespace'] = (attrs.get('namespace') or 'default').strip() or 'default'
            attrs['release_name'] = (attrs.get('release_name') or '').strip()

        return attrs
