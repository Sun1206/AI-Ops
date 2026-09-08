from rest_framework import serializers
from .models import CIType, ConfigItem, CIRelation, CostRecord, ResourceRequest, ResourceNode
from django.db.models import Sum
from .sync import normalize_ci_attributes, normalize_ci_type_name, resolve_config_item_type_meta

class CITypeSerializer(serializers.ModelSerializer):
    ci_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CIType
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['name'] = normalize_ci_type_name(data.get('name'))
        return data

    def validate_name(self, value):
        return normalize_ci_type_name(value)

class ConfigItemSerializer(serializers.ModelSerializer):
    ci_type_name = serializers.SerializerMethodField()
    ci_type_icon = serializers.SerializerMethodField()
    ci_type_color = serializers.SerializerMethodField()
    relation_count = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    environment_display = serializers.CharField(source='get_environment_display', read_only=True)

    class Meta:
        model = ConfigItem
        fields = '__all__'

    def get_ci_type_name(self, obj):
        return resolve_config_item_type_meta(obj)['name']

    def get_ci_type_icon(self, obj):
        return resolve_config_item_type_meta(obj)['icon']

    def get_ci_type_color(self, obj):
        return resolve_config_item_type_meta(obj)['color']

    def get_relation_count(self, obj):
        return obj.outgoing_relations.count() + obj.incoming_relations.count()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['attributes'] = normalize_ci_attributes(data.get('attributes'))
        return data

class CIRelationSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source='source.name', read_only=True)
    target_name = serializers.CharField(source='target.name', read_only=True)
    source_type = serializers.CharField(source='source.ci_type.name', read_only=True)
    target_type = serializers.CharField(source='target.ci_type.name', read_only=True)

    class Meta:
        model = CIRelation
        fields = '__all__'

    def validate(self, attrs):
        source = attrs.get('source') or getattr(self.instance, 'source', None)
        target = attrs.get('target') or getattr(self.instance, 'target', None)
        relation_type = attrs.get('relation_type') or getattr(self.instance, 'relation_type', None)

        if source and target and source.id == target.id:
            raise serializers.ValidationError('Source and target must be different CIs.')

        if source and target and relation_type:
            duplicate_qs = CIRelation.objects.filter(
                source=source,
                target=target,
                relation_type=relation_type,
            )
            if self.instance is not None:
                duplicate_qs = duplicate_qs.exclude(pk=self.instance.pk)
            if duplicate_qs.exists():
                raise serializers.ValidationError('This CI relation already exists.')

        return attrs

class CostRecordSerializer(serializers.ModelSerializer):
    ci_name = serializers.CharField(source='ci.name', read_only=True)
    business_line = serializers.CharField(source='ci.business_line', read_only=True)

    class Meta:
        model = CostRecord
        fields = '__all__'

class ResourceRequestSerializer(serializers.ModelSerializer):
    requester = serializers.CharField(source='applicant', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    environment_display = serializers.SerializerMethodField()

    class Meta:
        model = ResourceRequest
        fields = '__all__'
        read_only_fields = ['applicant', 'approver', 'approved_at', 'completed_at', 'created_at', 'updated_at']

    def get_environment_display(self, obj):
        return obj.get_environment_display() if obj.environment else ''

    def validate(self, attrs):
        business_line = (attrs.get('business_line') if 'business_line' in attrs else getattr(self.instance, 'business_line', '')) or ''
        environment = (attrs.get('environment') if 'environment' in attrs else getattr(self.instance, 'environment', '')) or ''
        title = (attrs.get('title') if 'title' in attrs else getattr(self.instance, 'title', '')) or ''
        resource_type = (attrs.get('resource_type') if 'resource_type' in attrs else getattr(self.instance, 'resource_type', '')) or ''
        quantity = attrs.get('quantity', getattr(self.instance, 'quantity', 1))

        business_line = business_line.strip()
        title = title.strip()
        resource_type = resource_type.strip()
        if not title:
            raise serializers.ValidationError({'title': '请填写申请标题'})
        normalized_resource_type = '主机' if resource_type in ['主机', 'host', 'Host', 'HOST'] else resource_type
        if normalized_resource_type != '主机':
            raise serializers.ValidationError({'resource_type': '当前仅支持主机申请'})
        if quantity < 1:
            raise serializers.ValidationError({'quantity': '数量必须大于 0'})
        if business_line and not ResourceNode.objects.filter(node_type='biz', name=business_line).exists():
            raise serializers.ValidationError({'business_line': '所选业务线未在资源树中配置'})
        if environment:
            if not business_line:
                raise serializers.ValidationError({'environment': '请先选择业务线'})
            if not ResourceNode.objects.filter(node_type='env', parent__name=business_line, name=environment).exists():
                raise serializers.ValidationError({'environment': '所选环境未在当前业务线下配置'})

        attrs['title'] = title
        attrs['resource_type'] = normalized_resource_type
        attrs['business_line'] = business_line
        return attrs

class ResourceNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceNode
        fields = '__all__'
