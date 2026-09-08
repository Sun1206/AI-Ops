from django.utils import timezone

from cmdb.models import CIType, CIRelation, ConfigItem

from .models import TerraformResourceBinding
from .terraform import build_render_payload


CI_TYPE_MAP = {
    'vpc': {'name': '云网络(VPC)', 'icon': 'Connection', 'color': '#2563eb'},
    'subnet': {'name': '子网(Subnet)', 'icon': 'Share', 'color': '#0ea5e9'},
    'security_group': {'name': '安全组', 'icon': 'Lock', 'color': '#475569'},
    'compute': {'name': '云主机(ECS)', 'icon': 'Monitor', 'color': '#22c55e'},
    'eip': {'name': '公网 IP(EIP)', 'icon': 'Position', 'color': '#f59e0b'},
    'rds': {'name': '数据库实例(RDS)', 'icon': 'Coin', 'color': '#8b5cf6'},
    'redis': {'name': '缓存实例(Redis)', 'icon': 'DataAnalysis', 'color': '#ef4444'},
    'load_balancer': {'name': '负载均衡', 'icon': 'Switch', 'color': '#14b8a6'},
    'nat_gateway': {'name': 'NAT 网关', 'icon': 'Link', 'color': '#f97316'},
    'object_storage': {'name': '对象存储', 'icon': 'FolderOpened', 'color': '#6366f1'},
}


def sync_stack_to_cmdb(stack, operator=''):
    payload = build_render_payload(
        name=stack.name,
        description=stack.description,
        cloud_provider=stack.cloud_provider,
        region=stack.region,
        zone=stack.zone,
        config=stack.config,
        secrets={},
    )
    inventory = payload['resource_inventory']
    metadata = payload['config']['metadata']
    business_line = metadata.get('business_line', '')
    environment = metadata.get('environment', 'prod')
    admin_user = metadata.get('owner') or operator or stack.updated_by or stack.created_by

    created = 0
    updated = 0
    bound = {}

    for resource in inventory:
        ci_type = _ensure_ci_type(resource['kind'])
        binding = TerraformResourceBinding.objects.filter(stack=stack, resource_key=resource['key']).select_related('cmdb_item').first()
        attributes = {
            **resource.get('metadata', {}),
            'cloud_provider': stack.cloud_provider,
            'region': stack.region,
            'zone': stack.zone,
            'iac_stack_id': stack.id,
            'iac_stack_name': stack.name,
            'iac_resource_key': resource['key'],
            'iac_resource_kind': resource['kind'],
            'synced_at': timezone.now().isoformat(),
        }
        if binding:
            item = binding.cmdb_item
            item.name = resource['name']
            item.ci_type = ci_type
            item.business_line = business_line
            item.environment = environment
            item.admin_user = admin_user
            item.status = 'active'
            item.attributes = attributes
            item.save()
            binding.resource_name = resource['name']
            binding.resource_kind = resource['kind']
            binding.metadata = resource.get('metadata', {})
            binding.save()
            updated += 1
        else:
            item = ConfigItem.objects.create(
                name=resource['name'],
                ci_type=ci_type,
                business_line=business_line,
                environment=environment,
                admin_user=admin_user,
                status='active',
                attributes=attributes,
            )
            TerraformResourceBinding.objects.create(
                stack=stack,
                resource_key=resource['key'],
                resource_name=resource['name'],
                resource_kind=resource['kind'],
                cmdb_item=item,
                metadata=resource.get('metadata', {}),
            )
            created += 1
        bound[resource['key']] = item

    for relation in payload.get('resource_relationships', []):
        _ensure_relation(
            bound,
            relation['source'],
            relation['target'],
            relation['relation_type'],
            relation.get('description') or '',
        )

    stack.last_cmdb_sync_at = timezone.now()
    stack.save(update_fields=['last_cmdb_sync_at'])

    return {
        'resource_count': len(inventory),
        'created_items': created,
        'updated_items': updated,
        'business_line': business_line,
        'environment': environment,
    }


def mark_stack_resources_offline(stack):
    count = 0
    for binding in TerraformResourceBinding.objects.filter(stack=stack).select_related('cmdb_item'):
        item = binding.cmdb_item
        item.status = 'offline'
        attrs = dict(item.attributes or {})
        attrs['destroyed_at'] = timezone.now().isoformat()
        item.attributes = attrs
        item.save(update_fields=['status', 'attributes', 'updated_at'])
        count += 1
    return {'resource_count': count, 'detail': '已将关联 CMDB 资源标记为离线。'}


def _ensure_ci_type(kind):
    meta = CI_TYPE_MAP[kind]
    ci_type, _ = CIType.objects.get_or_create(
        name=meta['name'],
        defaults={
            'icon': meta['icon'],
            'color': meta['color'],
            'description': f'由 Terraform IaC 自动同步的 {meta["name"]}',
        },
    )
    return ci_type


def _ensure_relation(bound, source_key, target_key, relation_type, description):
    source = bound.get(source_key)
    target = bound.get(target_key)
    if not source or not target:
        return
    CIRelation.objects.get_or_create(
        source=source,
        target=target,
        relation_type=relation_type,
        defaults={'description': description},
    )
