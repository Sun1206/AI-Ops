
import copy
import ipaddress
import re
from collections import OrderedDict

from rest_framework.exceptions import ValidationError


ENV_CHOICES = ['prod', 'test', 'dev']
RELATION_TYPE_OPTIONS = [
    {'value': 'depends_on', 'label': '依赖'},
    {'value': 'connects_to', 'label': '连接'},
    {'value': 'runs_on', 'label': '部署在'},
]


PROVIDER_CATALOG = {
    'aliyun': {
        'label': '阿里云',
        'provider_source': 'aliyun/alicloud',
        'provider_version': '~> 1.253.0',
        'provider_name': 'alicloud',
        'description': '生成阿里云 VPC、交换机、安全组、ECS，以及可选的 RDS、Redis、SLB、NAT 和 OSS Terraform 工程。',
        'default_stack_name': 'prod-web',
        'default_zone': 'cn-hangzhou-h',
        'regions': [
            {'value': 'cn-hangzhou', 'label': '华东 1（杭州）'},
            {'value': 'cn-shanghai', 'label': '华东 2（上海）'},
            {'value': 'cn-beijing', 'label': '华北 2（北京）'},
            {'value': 'cn-shenzhen', 'label': '华南 1（深圳）'},
        ],
        'zone_options': {
            'cn-hangzhou': [
                {'value': 'cn-hangzhou-h', 'label': '杭州可用区 H'},
                {'value': 'cn-hangzhou-i', 'label': '杭州可用区 I'},
            ],
            'cn-shanghai': [
                {'value': 'cn-shanghai-f', 'label': '上海可用区 F'},
                {'value': 'cn-shanghai-g', 'label': '上海可用区 G'},
            ],
            'cn-beijing': [
                {'value': 'cn-beijing-k', 'label': '北京可用区 K'},
                {'value': 'cn-beijing-l', 'label': '北京可用区 L'},
            ],
            'cn-shenzhen': [
                {'value': 'cn-shenzhen-f', 'label': '深圳可用区 F'},
                {'value': 'cn-shenzhen-g', 'label': '深圳可用区 G'},
            ],
        },
        'defaults': {
            'metadata': {'project_name': '', 'business_line': '', 'environment': 'prod', 'owner': ''},
            'network': {'vpc_cidr': '10.10.0.0/16', 'subnet_cidr': '10.10.1.0/24', 'open_ingress_ports': [22, 80, 443]},
            'compute': {
                'instance_name': 'prod-web-01',
                'instance_type': 'ecs.g6.large',
                'image_id': 'ubuntu_22_04_x64_20G_alibase_20240111.vhd',
                'system_disk_type': 'cloud_essd',
                'system_disk_size': 40,
                'public_bandwidth': 5,
                'instances': [
                    {
                        'instance_name': 'prod-web-01',
                        'instance_type': 'ecs.g6.large',
                        'image_id': 'ubuntu_22_04_x64_20G_alibase_20240111.vhd',
                        'system_disk_type': 'cloud_essd',
                        'system_disk_size': 40,
                        'public_bandwidth': 5,
                    }
                ],
            },
            'resources': {
                'rds': {'enabled': False, 'name': 'prod-mysql', 'instance_type': 'mysql.n2.medium.1', 'engine': 'MySQL', 'engine_version': '8.0', 'storage_gb': 20, 'db_name': 'appdb'},
                'redis': {'enabled': False, 'name': 'prod-redis', 'instance_class': 'redis.master.small.default', 'engine_version': '5.0'},
                'load_balancer': {'enabled': False, 'name': 'prod-slb', 'address_type': 'internet', 'spec': 'slb.s2.small'},
                'nat_gateway': {'enabled': False, 'name': 'prod-nat', 'bandwidth': 10},
                'object_storage': {
                    'enabled': False,
                    'bucket_name': 'sxdevops-prod-artifacts',
                    'acl': 'private',
                    'storage_class': 'Standard',
                    'buckets': [
                        {
                            'bucket_name': 'sxdevops-prod-artifacts',
                            'acl': 'private',
                            'storage_class': 'Standard',
                        }
                    ],
                },
            },
            'topology': {'relations': []},
        },
        'sections': [
            {'key': 'metadata', 'label': '治理信息', 'fields': [
                {'path': 'metadata.project_name', 'label': '项目标识', 'type': 'text'},
                {'path': 'metadata.business_line', 'label': '系统', 'type': 'text'},
                {'path': 'metadata.environment', 'label': '环境', 'type': 'select', 'options': ENV_CHOICES},
                {'path': 'metadata.owner', 'label': '负责人', 'type': 'text'},
            ]},
            {'key': 'network', 'label': '网络', 'fields': [
                {'path': 'network.vpc_cidr', 'label': 'VPC CIDR', 'type': 'text'},
                {'path': 'network.subnet_cidr', 'label': '交换机 CIDR', 'type': 'text'},
                {'path': 'network.open_ingress_ports', 'label': '开放端口', 'type': 'ports'},
            ]},
            {'key': 'compute', 'label': '服务器', 'fields': [
                {'path': 'compute.instance_name', 'label': 'ECS 实例名', 'type': 'text'},
                {'path': 'compute.instance_type', 'label': '实例规格', 'type': 'text'},
                {'path': 'compute.image_id', 'label': '镜像 ID', 'type': 'text'},
                {'path': 'compute.system_disk_type', 'label': '系统盘类型', 'type': 'select', 'options': ['cloud_essd', 'cloud_efficiency', 'cloud_ssd']},
                {'path': 'compute.system_disk_size', 'label': '系统盘大小(GB)', 'type': 'number', 'min': 40, 'max': 500},
                {'path': 'compute.public_bandwidth', 'label': '公网带宽(Mbps)', 'type': 'number', 'min': 0, 'max': 100},
            ]},
            {'key': 'rds', 'label': 'RDS', 'fields': [
                {'path': 'resources.rds.enabled', 'label': '启用 RDS', 'type': 'switch'},
                {'path': 'resources.rds.name', 'label': 'RDS 名称', 'type': 'text'},
                {'path': 'resources.rds.instance_type', 'label': 'RDS 规格', 'type': 'text'},
                {'path': 'resources.rds.engine', 'label': '数据库引擎', 'type': 'select', 'options': ['MySQL', 'PostgreSQL']},
                {'path': 'resources.rds.engine_version', 'label': '引擎版本', 'type': 'text'},
                {'path': 'resources.rds.storage_gb', 'label': '存储(GB)', 'type': 'number', 'min': 20, 'max': 2000},
                {'path': 'resources.rds.db_name', 'label': '默认库名', 'type': 'text'},
            ]},
            {'key': 'redis', 'label': 'Redis', 'fields': [
                {'path': 'resources.redis.enabled', 'label': '启用 Redis', 'type': 'switch'},
                {'path': 'resources.redis.name', 'label': 'Redis 名称', 'type': 'text'},
                {'path': 'resources.redis.instance_class', 'label': '实例规格', 'type': 'text'},
                {'path': 'resources.redis.engine_version', 'label': '引擎版本', 'type': 'text'},
            ]},
            {'key': 'load_balancer', 'label': 'SLB', 'fields': [
                {'path': 'resources.load_balancer.enabled', 'label': '启用 SLB', 'type': 'switch'},
                {'path': 'resources.load_balancer.name', 'label': 'SLB 名称', 'type': 'text'},
                {'path': 'resources.load_balancer.address_type', 'label': '地址类型', 'type': 'select', 'options': ['internet', 'intranet']},
                {'path': 'resources.load_balancer.spec', 'label': 'SLB 规格', 'type': 'text'},
            ]},
            {'key': 'nat_gateway', 'label': 'NAT 网关', 'fields': [
                {'path': 'resources.nat_gateway.enabled', 'label': '启用 NAT', 'type': 'switch'},
                {'path': 'resources.nat_gateway.name', 'label': 'NAT 名称', 'type': 'text'},
                {'path': 'resources.nat_gateway.bandwidth', 'label': 'EIP 带宽(Mbps)', 'type': 'number', 'min': 1, 'max': 200},
            ]},
            {'key': 'object_storage', 'label': '对象存储', 'fields': [
                {'path': 'resources.object_storage.enabled', 'label': '启用 OSS', 'type': 'switch'},
                {'path': 'resources.object_storage.bucket_name', 'label': 'Bucket 名称', 'type': 'text'},
                {'path': 'resources.object_storage.acl', 'label': '访问控制', 'type': 'select', 'options': ['private', 'public-read']},
                {'path': 'resources.object_storage.storage_class', 'label': '存储类型', 'type': 'select', 'options': ['Standard', 'IA', 'Archive']},
            ]},
        ],
        'secret_fields': [
            {'key': 'access_key', 'label': 'Access Key', 'type': 'password', 'required': True},
            {'key': 'secret_key', 'label': 'Secret Key', 'type': 'password', 'required': True},
            {'key': 'instance_password', 'label': '实例登录密码', 'type': 'password', 'required': True},
            {'key': 'db_password', 'label': 'RDS 管理密码', 'type': 'password', 'required': False},
            {'key': 'redis_password', 'label': 'Redis 密码', 'type': 'password', 'required': False},
        ],
        'relation_types': RELATION_TYPE_OPTIONS,
    },
    'huaweicloud': {
        'label': '华为云',
        'provider_source': 'huaweicloud/huaweicloud',
        'provider_version': '~> 1.71.0',
        'provider_name': 'huaweicloud',
        'description': '生成华为云 VPC、子网、安全组、ECS、EIP，以及可选的 RDS、Redis、ELB、NAT 和 OBS Terraform 工程。',
        'default_stack_name': 'prod-web',
        'default_zone': 'cn-north-4a',
        'regions': [
            {'value': 'cn-north-4', 'label': '华北-北京四'},
            {'value': 'cn-east-3', 'label': '华东-上海一'},
            {'value': 'cn-south-1', 'label': '华南-广州'},
            {'value': 'ap-southeast-3', 'label': '亚太-新加坡'},
        ],
        'zone_options': {
            'cn-north-4': [
                {'value': 'cn-north-4a', 'label': '北京四可用区 A'},
                {'value': 'cn-north-4b', 'label': '北京四可用区 B'},
            ],
            'cn-east-3': [
                {'value': 'cn-east-3a', 'label': '上海一可用区 A'},
                {'value': 'cn-east-3b', 'label': '上海一可用区 B'},
            ],
            'cn-south-1': [
                {'value': 'cn-south-1a', 'label': '广州可用区 A'},
                {'value': 'cn-south-1b', 'label': '广州可用区 B'},
            ],
            'ap-southeast-3': [
                {'value': 'ap-southeast-3a', 'label': '新加坡可用区 A'},
                {'value': 'ap-southeast-3b', 'label': '新加坡可用区 B'},
            ],
        },
        'defaults': {
            'metadata': {'project_name': '', 'business_line': '', 'environment': 'prod', 'owner': ''},
            'network': {'vpc_cidr': '10.20.0.0/16', 'subnet_cidr': '10.20.1.0/24', 'open_ingress_ports': [22, 80, 443]},
            'compute': {
                'instance_name': 'prod-web-01',
                'instance_type': 's7n.large.2',
                'image_id': 'replace-with-image-id',
                'system_disk_type': 'SSD',
                'system_disk_size': 40,
                'public_bandwidth': 5,
                'instances': [
                    {
                        'instance_name': 'prod-web-01',
                        'instance_type': 's7n.large.2',
                        'image_id': 'replace-with-image-id',
                        'system_disk_type': 'SSD',
                        'system_disk_size': 40,
                        'public_bandwidth': 5,
                    }
                ],
            },
            'resources': {
                'rds': {'enabled': False, 'name': 'prod-mysql', 'flavor': 'rds.mysql.n1.medium.2', 'engine': 'MySQL', 'engine_version': '8.0', 'storage_gb': 40, 'volume_type': 'CLOUDSSD', 'db_name': 'appdb'},
                'redis': {'enabled': False, 'name': 'prod-redis', 'capacity': 1, 'engine_version': '5.0', 'flavor': 'redis.ha.xu1.large.r2.2'},
                'load_balancer': {'enabled': False, 'name': 'prod-elb', 'bandwidth': 10, 'type': 'External'},
                'nat_gateway': {'enabled': False, 'name': 'prod-nat', 'spec': '1'},
                'object_storage': {
                    'enabled': False,
                    'bucket_name': 'sxdevops-prod-artifacts',
                    'acl': 'private',
                    'storage_class': 'STANDARD',
                    'buckets': [
                        {
                            'bucket_name': 'sxdevops-prod-artifacts',
                            'acl': 'private',
                            'storage_class': 'STANDARD',
                        }
                    ],
                },
            },
            'topology': {'relations': []},
        },
        'sections': [
            {'key': 'metadata', 'label': '治理信息', 'fields': [
                {'path': 'metadata.project_name', 'label': '项目标识', 'type': 'text'},
                {'path': 'metadata.business_line', 'label': '系统', 'type': 'text'},
                {'path': 'metadata.environment', 'label': '环境', 'type': 'select', 'options': ENV_CHOICES},
                {'path': 'metadata.owner', 'label': '负责人', 'type': 'text'},
            ]},
            {'key': 'network', 'label': '网络', 'fields': [
                {'path': 'network.vpc_cidr', 'label': 'VPC CIDR', 'type': 'text'},
                {'path': 'network.subnet_cidr', 'label': '子网 CIDR', 'type': 'text'},
                {'path': 'network.open_ingress_ports', 'label': '开放端口', 'type': 'ports'},
            ]},
            {'key': 'compute', 'label': '服务器', 'fields': [
                {'path': 'compute.instance_name', 'label': 'ECS 实例名', 'type': 'text'},
                {'path': 'compute.instance_type', 'label': '规格 ID', 'type': 'text'},
                {'path': 'compute.image_id', 'label': '镜像 ID', 'type': 'text'},
                {'path': 'compute.system_disk_type', 'label': '系统盘类型', 'type': 'select', 'options': ['SSD', 'SAS', 'GPSSD']},
                {'path': 'compute.system_disk_size', 'label': '系统盘大小(GB)', 'type': 'number', 'min': 40, 'max': 1024},
                {'path': 'compute.public_bandwidth', 'label': '公网带宽(Mbps)', 'type': 'number', 'min': 0, 'max': 300},
            ]},
            {'key': 'rds', 'label': 'RDS', 'fields': [
                {'path': 'resources.rds.enabled', 'label': '启用 RDS', 'type': 'switch'},
                {'path': 'resources.rds.name', 'label': 'RDS 名称', 'type': 'text'},
                {'path': 'resources.rds.flavor', 'label': 'RDS Flavor', 'type': 'text'},
                {'path': 'resources.rds.engine', 'label': '数据库引擎', 'type': 'select', 'options': ['MySQL', 'PostgreSQL']},
                {'path': 'resources.rds.engine_version', 'label': '引擎版本', 'type': 'text'},
                {'path': 'resources.rds.storage_gb', 'label': '存储(GB)', 'type': 'number', 'min': 40, 'max': 4000},
                {'path': 'resources.rds.volume_type', 'label': '存储类型', 'type': 'select', 'options': ['CLOUDSSD', 'ULTRAHIGH', 'COMMON']},
                {'path': 'resources.rds.db_name', 'label': '默认库名', 'type': 'text'},
            ]},
            {'key': 'redis', 'label': 'Redis', 'fields': [
                {'path': 'resources.redis.enabled', 'label': '启用 Redis', 'type': 'switch'},
                {'path': 'resources.redis.name', 'label': 'Redis 名称', 'type': 'text'},
                {'path': 'resources.redis.capacity', 'label': '容量(GB)', 'type': 'number', 'min': 1, 'max': 64},
                {'path': 'resources.redis.engine_version', 'label': '引擎版本', 'type': 'text'},
                {'path': 'resources.redis.flavor', 'label': 'Flavor', 'type': 'text'},
            ]},
            {'key': 'load_balancer', 'label': 'ELB', 'fields': [
                {'path': 'resources.load_balancer.enabled', 'label': '启用 ELB', 'type': 'switch'},
                {'path': 'resources.load_balancer.name', 'label': 'ELB 名称', 'type': 'text'},
                {'path': 'resources.load_balancer.bandwidth', 'label': '带宽(Mbps)', 'type': 'number', 'min': 1, 'max': 300},
                {'path': 'resources.load_balancer.type', 'label': 'ELB 类型', 'type': 'select', 'options': ['External', 'Internal']},
            ]},
            {'key': 'nat_gateway', 'label': 'NAT 网关', 'fields': [
                {'path': 'resources.nat_gateway.enabled', 'label': '启用 NAT', 'type': 'switch'},
                {'path': 'resources.nat_gateway.name', 'label': 'NAT 名称', 'type': 'text'},
                {'path': 'resources.nat_gateway.spec', 'label': 'NAT 规格', 'type': 'text'},
            ]},
            {'key': 'object_storage', 'label': '对象存储', 'fields': [
                {'path': 'resources.object_storage.enabled', 'label': '启用 OBS', 'type': 'switch'},
                {'path': 'resources.object_storage.bucket_name', 'label': 'Bucket 名称', 'type': 'text'},
                {'path': 'resources.object_storage.acl', 'label': '访问控制', 'type': 'select', 'options': ['private', 'public-read']},
                {'path': 'resources.object_storage.storage_class', 'label': '存储类型', 'type': 'select', 'options': ['STANDARD', 'WARM', 'COLD']},
            ]},
        ],
        'secret_fields': [
            {'key': 'access_key', 'label': 'Access Key', 'type': 'password', 'required': True},
            {'key': 'secret_key', 'label': 'Secret Key', 'type': 'password', 'required': True},
            {'key': 'instance_password', 'label': '实例登录密码', 'type': 'password', 'required': True},
            {'key': 'db_password', 'label': 'RDS 管理密码', 'type': 'password', 'required': False},
            {'key': 'redis_password', 'label': 'Redis 密码', 'type': 'password', 'required': False},
        ],
        'relation_types': RELATION_TYPE_OPTIONS,
    },
}


def build_render_payload(*, name, description, cloud_provider, region, zone, config, secrets):
    provider_meta = PROVIDER_CATALOG.get(cloud_provider)
    if not provider_meta:
        raise ValidationError({'cloud_provider': '暂不支持该云厂商。'})

    normalized_region = _normalize_region(provider_meta, region)
    normalized_zone = _normalize_zone(provider_meta, normalized_region, zone)
    normalized_name = _normalize_stack_name(name, default_name=provider_meta.get('default_stack_name'))
    normalized_config = _normalize_config(cloud_provider, config or {}, stack_name=normalized_name)
    normalized_secrets = _normalize_secrets(cloud_provider, normalized_config, secrets or {})

    payload = {
        'name': normalized_name,
        'display_name': str(name or normalized_name).strip() or normalized_name,
        'description': (description or '').strip(),
        'cloud_provider': cloud_provider,
        'provider_meta': provider_meta,
        'region': normalized_region,
        'zone': normalized_zone,
        'config': normalized_config,
        'secrets': normalized_secrets,
    }
    payload['resource_inventory'] = build_resource_inventory(payload)
    payload['resource_relationships'] = build_resource_relationships(payload)
    return payload


def render_terraform_project(payload):
    files = OrderedDict()
    files['versions.tf'] = _build_versions_tf(payload['provider_meta'])
    files['provider.tf'] = _build_provider_tf(payload)
    files['variables.tf'] = _build_variables_tf(payload)
    files['main.tf'] = _build_main_tf(payload)
    files['outputs.tf'] = _build_outputs_tf(payload)
    files['terraform.tfvars.example'] = _build_tfvars(payload, secrets=None)
    if payload['secrets']:
        files['terraform.tfvars'] = _build_tfvars(payload, secrets=payload['secrets'])
    files['README.md'] = _build_readme(payload, has_secret_tfvars=bool(payload['secrets']))

    return {
        'summary': {
            'provider': payload['cloud_provider'],
            'provider_label': payload['provider_meta']['label'],
            'region': payload['region'],
            'zone': payload['zone'],
            'metadata': payload['config']['metadata'],
            'network': payload['config']['network'],
            'compute': payload['config']['compute'],
            'compute_instances': payload['config']['compute'].get('instances', []),
            'topology': payload['config'].get('topology', {'relations': []}),
            'object_storage_buckets': payload['config']['resources']['object_storage'].get('buckets', []),
            'resources': payload['resource_inventory'],
            'relationships': payload['resource_relationships'],
            'relation_count': len(payload['resource_relationships']),
            'resource_count': len(payload['resource_inventory']),
        },
        'files': files,
    }


def _compute_resource_key(index):
    return 'compute' if index == 0 else f'compute_{index + 1}'


def _compute_resource_label(cloud_provider, index):
    base = 'ECS' if cloud_provider == 'aliyun' else 'ECS'
    return base if index == 0 else f'{base} {index + 1}'


def _eip_resource_key(index):
    return 'eip' if index == 0 else f'eip_{index + 1}'


def _object_storage_resource_key(index):
    return 'object_storage' if index == 0 else f'object_storage_{index + 1}'


def _get_compute_instances(config):
    instances = config.get('compute', {}).get('instances') or []
    return [item for item in instances if isinstance(item, dict)]


def _get_enabled_buckets(config):
    object_storage = config.get('resources', {}).get('object_storage', {})
    if not object_storage.get('enabled'):
        return []
    buckets = object_storage.get('buckets') or []
    return [item for item in buckets if isinstance(item, dict)]


def build_resource_inventory(payload):
    config = payload['config']
    resources = config['resources']
    compute_instances = _get_compute_instances(config)
    bucket_items = _get_enabled_buckets(config)
    inventory = [
        {'key': 'vpc', 'kind': 'vpc', 'label': 'VPC', 'name': f'{payload["name"]}-vpc', 'category': 'network', 'metadata': {'cidr': config['network']['vpc_cidr']}},
        {'key': 'subnet', 'kind': 'subnet', 'label': 'Subnet', 'name': f'{payload["name"]}-subnet', 'category': 'network', 'metadata': {'cidr': config['network']['subnet_cidr']}},
        {'key': 'security_group', 'kind': 'security_group', 'label': 'Security Group', 'name': f'{payload["name"]}-sg', 'category': 'security', 'metadata': {'ports': config['network']['open_ingress_ports']}},
    ]
    for index, instance in enumerate(compute_instances):
        inventory.append({
            'key': _compute_resource_key(index),
            'kind': 'compute',
            'label': _compute_resource_label(payload['cloud_provider'], index),
            'name': instance['instance_name'],
            'category': 'compute',
            'metadata': {
                'instance_type': instance['instance_type'],
                'image_id': instance['image_id'],
                'system_disk_type': instance['system_disk_type'],
                'system_disk_size': instance['system_disk_size'],
                'public_bandwidth': instance['public_bandwidth'],
                'index': index,
            },
        })
        if payload['cloud_provider'] == 'huaweicloud' and instance['public_bandwidth'] > 0:
            inventory.append({
                'key': _eip_resource_key(index),
                'kind': 'eip',
                'label': 'EIP' if index == 0 else f'EIP {index + 1}',
                'name': f'{payload["name"]}-eip-{index + 1:02d}',
                'category': 'network',
                'metadata': {'bandwidth': instance['public_bandwidth'], 'instance_key': _compute_resource_key(index)},
            })
    for key, label, category in [
        ('rds', 'RDS', 'database'),
        ('redis', 'Redis', 'cache'),
        ('load_balancer', 'Load Balancer', 'network'),
        ('nat_gateway', 'NAT Gateway', 'network'),
    ]:
        if resources[key]['enabled']:
            inventory.append({'key': key, 'kind': key, 'label': label, 'name': resources[key]['name'], 'category': category, 'metadata': resources[key]})
    for index, bucket in enumerate(bucket_items):
        inventory.append({
            'key': _object_storage_resource_key(index),
            'kind': 'object_storage',
            'label': 'Object Storage' if index == 0 else f'Object Storage {index + 1}',
            'name': bucket['bucket_name'],
            'category': 'storage',
            'metadata': {**bucket, 'index': index},
        })
    return inventory


def build_resource_relationships(payload):
    inventory_map = {item['key']: item for item in payload['resource_inventory']}
    combined = OrderedDict()

    for relation in _default_resource_relations(payload):
        key = (relation['source'], relation['target'], relation['relation_type'])
        combined[key] = {
            **relation,
            'source_name': inventory_map[relation['source']]['name'],
            'target_name': inventory_map[relation['target']]['name'],
            'mode': 'default',
        }

    for relation in payload['config'].get('topology', {}).get('relations', []):
        key = (relation['source'], relation['target'], relation['relation_type'])
        merged = {
            **relation,
            'source_name': inventory_map[relation['source']]['name'],
            'target_name': inventory_map[relation['target']]['name'],
            'mode': 'custom',
        }
        if key in combined:
            current = combined[key]
            current.update(merged)
            current['description'] = merged['description'] or current.get('description', '')
            current['mode'] = 'custom'
        else:
            combined[key] = merged

    return list(combined.values())


def _default_resource_relations(payload):
    relations = [
        {'source': 'subnet', 'target': 'vpc', 'relation_type': 'depends_on', 'description': 'Subnet depends on VPC'},
        {'source': 'security_group', 'target': 'vpc', 'relation_type': 'depends_on', 'description': 'Security group depends on VPC'},
    ]
    resource_keys = {item['key'] for item in payload['resource_inventory']}
    compute_keys = [item['key'] for item in payload['resource_inventory'] if item['kind'] == 'compute']
    bucket_keys = [item['key'] for item in payload['resource_inventory'] if item['kind'] == 'object_storage']
    optional_relations = [
        {'source': 'nat_gateway', 'target': 'subnet', 'relation_type': 'depends_on', 'description': 'NAT gateway depends on subnet'},
        {'source': 'rds', 'target': 'subnet', 'relation_type': 'depends_on', 'description': 'RDS depends on subnet'},
        {'source': 'redis', 'target': 'subnet', 'relation_type': 'depends_on', 'description': 'Redis depends on subnet'},
    ]
    for index, compute_key in enumerate(compute_keys):
        optional_relations.extend([
            {'source': compute_key, 'target': 'subnet', 'relation_type': 'depends_on', 'description': 'Compute depends on subnet'},
            {'source': compute_key, 'target': 'security_group', 'relation_type': 'depends_on', 'description': 'Compute depends on security group'},
        ])
        if 'load_balancer' in resource_keys:
            optional_relations.append({'source': 'load_balancer', 'target': compute_key, 'relation_type': 'connects_to', 'description': 'Load balancer routes to compute'})
        if 'rds' in resource_keys:
            optional_relations.append({'source': compute_key, 'target': 'rds', 'relation_type': 'depends_on', 'description': 'Application host depends on RDS'})
        if 'redis' in resource_keys:
            optional_relations.append({'source': compute_key, 'target': 'redis', 'relation_type': 'depends_on', 'description': 'Application host depends on Redis'})
        for bucket_key in bucket_keys:
            optional_relations.append({'source': compute_key, 'target': bucket_key, 'relation_type': 'depends_on', 'description': 'Application host depends on object storage'})
        eip_key = _eip_resource_key(index)
        if eip_key in resource_keys:
            optional_relations.append({'source': compute_key, 'target': eip_key, 'relation_type': 'depends_on', 'description': 'Compute depends on EIP'})
    relations.extend([
        relation for relation in optional_relations
        if relation['source'] in resource_keys and relation['target'] in resource_keys
    ])
    return relations


def _available_resource_keys(cloud_provider, config):
    keys = ['vpc', 'subnet', 'security_group', 'compute']
    if cloud_provider == 'huaweicloud' and int(config['compute'].get('public_bandwidth') or 0) > 0:
        keys.append('eip')
    for key in ['rds', 'redis', 'load_balancer', 'nat_gateway', 'object_storage']:
        if config['resources'][key]['enabled']:
            keys.append(key)
    return keys


def _normalize_stack_name(name, default_name=''):
    value = str(name or '').strip()
    if not value:
        value = str(default_name or '').strip()
    if not value:
        raise ValidationError({'name': '方案名称不能为空。'})
    if re.search(r'[\\/:*?"<>|]', value):
        raise ValidationError({'name': '方案名称不能包含 \\ / : * ? " < > |。'})
    if len(value) > 64:
        raise ValidationError({'name': '方案名称长度不能超过 64。'})
    return value


def _normalize_region(provider_meta, region):
    value = str(region or '').strip()
    if value:
        return value
    regions = provider_meta.get('regions') or []
    fallback = str((regions[0] or {}).get('value') or '').strip() if regions else ''
    if fallback:
        return fallback
    raise ValidationError({'region': '区域不能为空。'})


def _normalize_zone(provider_meta, region, zone):
    value = str(zone or '').strip()
    if value:
        return value

    region_options = (provider_meta.get('zone_options') or {}).get(region) or []
    if region_options:
        fallback = str((region_options[0] or {}).get('value') or '').strip()
        if fallback:
            return fallback

    fallback = str(provider_meta.get('default_zone') or '').strip()
    if fallback:
        return fallback
    raise ValidationError({'zone': '可用区不能为空。'})


def _normalize_config(cloud_provider, raw_config, stack_name=''):
    defaults = copy.deepcopy(PROVIDER_CATALOG[cloud_provider]['defaults'])
    prepared = _upgrade_legacy_config(raw_config, defaults)
    merged = _deep_merge(defaults, prepared)
    metadata = merged['metadata']
    network = merged['network']
    compute = merged['compute']
    resources = merged['resources']
    raw_compute = _as_dict((raw_config or {}).get('compute'))

    metadata['project_name'] = str(metadata.get('project_name') or '').strip()
    metadata['business_line'] = str(metadata.get('business_line') or '').strip()
    metadata['owner'] = str(metadata.get('owner') or '').strip()
    metadata['environment'] = str(metadata.get('environment') or 'prod').strip() or 'prod'
    if metadata['environment'] not in ENV_CHOICES:
        raise ValidationError({'config': 'environment 只能是 prod/test/dev。'})

    vpc_network = _parse_network(network['vpc_cidr'], 'network.vpc_cidr')
    subnet_network = _parse_network(network['subnet_cidr'], 'network.subnet_cidr')
    if not subnet_network.subnet_of(vpc_network):
        raise ValidationError({'config': '子网网段必须包含在 VPC 网段内。'})
    network['vpc_cidr'] = str(vpc_network)
    network['subnet_cidr'] = str(subnet_network)
    network['open_ingress_ports'] = _normalize_ports(network.get('open_ingress_ports'))
    if cloud_provider == 'huaweicloud':
        network['subnet_gateway'] = str(next(subnet_network.hosts()))

    compute_instances = _normalize_compute_instances(
        raw_config=raw_config or {},
        raw_compute=raw_compute,
        merged_compute=compute,
        stack_name=stack_name,
    )
    compute.update(copy.deepcopy(compute_instances[0]))
    compute['instances'] = compute_instances

    for key in ['rds', 'redis', 'load_balancer', 'nat_gateway', 'object_storage']:
        resources[key]['enabled'] = bool(resources[key].get('enabled'))
    if resources['rds']['enabled']:
        _normalize_rds(cloud_provider, resources['rds'])
    if resources['redis']['enabled']:
        _normalize_redis(cloud_provider, resources['redis'])
    if resources['load_balancer']['enabled']:
        _normalize_load_balancer(cloud_provider, resources['load_balancer'])
    if resources['nat_gateway']['enabled']:
        _normalize_nat_gateway(cloud_provider, resources['nat_gateway'])
    resources['object_storage'] = _normalize_object_storage(cloud_provider, resources['object_storage'])
    merged['topology'] = _normalize_topology(cloud_provider, merged)
    return merged


def _normalize_rds(cloud_provider, config):
    config['name'] = str(config.get('name') or '').strip()
    config['engine'] = str(config.get('engine') or '').strip() or 'MySQL'
    config['engine_version'] = str(config.get('engine_version') or '').strip() or '8.0'
    config['db_name'] = _normalize_identifier(config.get('db_name') or 'appdb', 'RDS 库名')
    config['storage_gb'] = _coerce_int(config.get('storage_gb'), 'resources.rds.storage_gb', 20)
    if not config['name']:
        raise ValidationError({'config': '启用 RDS 时必须填写资源名称。'})
    if cloud_provider == 'aliyun':
        config['instance_type'] = str(config.get('instance_type') or '').strip()
        if not config['instance_type']:
            raise ValidationError({'config': '阿里云 RDS 需要 instance_type。'})
    else:
        config['flavor'] = str(config.get('flavor') or '').strip()
        config['volume_type'] = str(config.get('volume_type') or 'CLOUDSSD').strip() or 'CLOUDSSD'
        if not config['flavor']:
            raise ValidationError({'config': '华为云 RDS 需要 flavor。'})


def _normalize_redis(cloud_provider, config):
    config['name'] = str(config.get('name') or '').strip()
    config['engine_version'] = str(config.get('engine_version') or '').strip() or '5.0'
    if not config['name']:
        raise ValidationError({'config': '启用 Redis 时必须填写资源名称。'})
    if cloud_provider == 'aliyun':
        config['instance_class'] = str(config.get('instance_class') or '').strip()
        if not config['instance_class']:
            raise ValidationError({'config': '阿里云 Redis 需要 instance_class。'})
    else:
        config['capacity'] = _coerce_int(config.get('capacity'), 'resources.redis.capacity', 1)
        config['flavor'] = str(config.get('flavor') or '').strip()
        if not config['flavor']:
            raise ValidationError({'config': '华为云 Redis 需要 flavor。'})


def _normalize_load_balancer(cloud_provider, config):
    config['name'] = str(config.get('name') or '').strip()
    if not config['name']:
        raise ValidationError({'config': '启用负载均衡时必须填写资源名称。'})
    if cloud_provider == 'aliyun':
        config['address_type'] = str(config.get('address_type') or 'internet').strip() or 'internet'
        config['spec'] = str(config.get('spec') or '').strip() or 'slb.s2.small'
    else:
        config['type'] = str(config.get('type') or 'External').strip() or 'External'
        config['bandwidth'] = _coerce_int(config.get('bandwidth'), 'resources.load_balancer.bandwidth', 1)


def _normalize_nat_gateway(cloud_provider, config):
    config['name'] = str(config.get('name') or '').strip()
    if not config['name']:
        raise ValidationError({'config': '启用 NAT 网关时必须填写资源名称。'})
    if cloud_provider == 'aliyun':
        config['bandwidth'] = _coerce_int(config.get('bandwidth'), 'resources.nat_gateway.bandwidth', 1)
    else:
        config['spec'] = str(config.get('spec') or '').strip() or '1'


def _normalize_compute_instances(*, raw_config, raw_compute, merged_compute, stack_name):
    default_instance = {
        'instance_name': _first_non_empty(merged_compute.get('instance_name'), stack_name),
        'instance_type': _first_non_empty(merged_compute.get('instance_type')),
        'image_id': _first_non_empty(merged_compute.get('image_id')),
        'system_disk_type': str(merged_compute.get('system_disk_type') or '').strip(),
        'system_disk_size': merged_compute.get('system_disk_size'),
        'public_bandwidth': merged_compute.get('public_bandwidth'),
    }
    raw_instances = raw_compute.get('instances') if isinstance(raw_compute.get('instances'), list) else []
    instance_sources = []
    for item in raw_instances:
        if isinstance(item, dict):
            instance_sources.append(item)
    if not instance_sources:
        instance_sources = [raw_compute if raw_compute else {}]

    normalized = []
    for index, item in enumerate(instance_sources):
        candidate = copy.deepcopy(default_instance)
        candidate.update(_as_dict(item))
        fallback_name = stack_name if index == 0 else f'{stack_name}-{index + 1:02d}'
        instance = {
            'instance_name': _first_non_empty(
                _as_dict(item).get('instance_name'),
                _as_dict(item).get('name'),
                raw_compute.get('instance_name') if index == 0 else '',
                raw_compute.get('name') if index == 0 else '',
                raw_config.get('instance_name') if index == 0 else '',
                fallback_name,
                candidate.get('instance_name'),
                candidate.get('name'),
            ),
            'instance_type': _first_non_empty(
                candidate.get('instance_type'),
                candidate.get('flavor_id'),
                raw_compute.get('instance_type') if index == 0 else '',
                raw_compute.get('flavor_id') if index == 0 else '',
                raw_config.get('instance_type') if index == 0 else '',
                default_instance.get('instance_type'),
            ),
            'image_id': _first_non_empty(
                candidate.get('image_id'),
                raw_compute.get('image_id') if index == 0 else '',
                raw_config.get('image_id') if index == 0 else '',
                default_instance.get('image_id'),
            ),
            'system_disk_type': str(candidate.get('system_disk_type') or default_instance.get('system_disk_type') or '').strip(),
            'system_disk_size': _coerce_int(candidate.get('system_disk_size'), f'compute.instances[{index}].system_disk_size', 40),
            'public_bandwidth': _coerce_int(candidate.get('public_bandwidth'), f'compute.instances[{index}].public_bandwidth', 0),
        }
        if not instance['instance_name'] or not instance['instance_type'] or not instance['image_id']:
            raise ValidationError({'config': f'服务器 {index + 1} 的名称、规格、镜像 ID 都不能为空。'})
        normalized.append(instance)
    return normalized


def _normalize_object_storage(cloud_provider, config):
    bucket_defaults = {
        'bucket_name': config.get('bucket_name'),
        'acl': config.get('acl') or 'private',
        'storage_class': config.get('storage_class') or ('Standard' if cloud_provider == 'aliyun' else 'STANDARD'),
    }
    raw_buckets = config.get('buckets') if isinstance(config.get('buckets'), list) else []
    bucket_sources = []
    for item in raw_buckets:
        if isinstance(item, dict):
            bucket_sources.append(item)
    if not bucket_sources:
        bucket_sources = [bucket_defaults]

    normalized_buckets = []
    for index, bucket in enumerate(bucket_sources):
        candidate = {**bucket_defaults, **_as_dict(bucket)}
        normalized_buckets.append({
            'bucket_name': _normalize_bucket_name(_first_non_empty(candidate.get('bucket_name'), bucket_defaults.get('bucket_name'), f'sxdevops-bucket-{index + 1}')),
            'acl': str(candidate.get('acl') or 'private').strip() or 'private',
            'storage_class': str(candidate.get('storage_class') or bucket_defaults['storage_class']).strip(),
        })

    config['enabled'] = bool(config.get('enabled'))
    config['buckets'] = normalized_buckets
    primary_bucket = normalized_buckets[0]
    config['bucket_name'] = primary_bucket['bucket_name']
    config['acl'] = primary_bucket['acl']
    config['storage_class'] = primary_bucket['storage_class']
    return config


def _normalize_topology(cloud_provider, config):
    topology = _as_dict(config.get('topology'))
    available_keys = set(_available_resource_keys(cloud_provider, config))
    supported_types = {item['value'] for item in RELATION_TYPE_OPTIONS}
    normalized_relations = []
    seen = set()

    for index, raw_relation in enumerate(topology.get('relations') or []):
        relation = _as_dict(raw_relation)
        source = str(relation.get('source') or '').strip()
        target = str(relation.get('target') or '').strip()
        relation_type = str(relation.get('relation_type') or 'depends_on').strip() or 'depends_on'
        description = str(relation.get('description') or '').strip()

        if not any([source, target, description, relation.get('relation_type')]):
            continue
        if not source or not target:
            raise ValidationError({'config': f'topology.relations[{index}] 需要同时填写 source 和 target。'})
        if source == target:
            raise ValidationError({'config': f'topology.relations[{index}] 的 source 和 target 不能相同。'})
        if source not in available_keys or target not in available_keys:
            raise ValidationError({'config': f'topology.relations[{index}] 只能引用当前已启用的资源。'})
        if relation_type not in supported_types:
            raise ValidationError({'config': f'topology.relations[{index}] 的 relation_type 不支持。'})

        dedupe_key = (source, target, relation_type)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized_relations.append({
            'source': source,
            'target': target,
            'relation_type': relation_type,
            'description': description,
        })

    return {'relations': normalized_relations}


def _normalize_secrets(cloud_provider, config, secrets):
    if not secrets:
        return {}
    normalized = {}
    for field in PROVIDER_CATALOG[cloud_provider]['secret_fields']:
        key = field['key']
        value = str((secrets or {}).get(key, '')).strip()
        if field.get('required') and not value:
            raise ValidationError({'secrets': f'导出或执行时缺少敏感参数: {key}'})
        if value:
            normalized[key] = value
    if config['resources']['rds']['enabled'] and not normalized.get('db_password'):
        raise ValidationError({'secrets': '启用 RDS 时需要提供 db_password。'})
    if config['resources']['redis']['enabled'] and cloud_provider == 'huaweicloud' and not normalized.get('redis_password'):
        raise ValidationError({'secrets': '启用华为云 Redis 时需要提供 redis_password。'})
    return normalized


def _upgrade_legacy_config(raw_config, defaults):
    if not isinstance(raw_config, dict) or not raw_config:
        return {}
    raw_config = copy.deepcopy(raw_config)
    for key in ['metadata', 'network', 'compute', 'resources', 'topology']:
        if key in raw_config and not isinstance(raw_config[key], dict):
            raw_config[key] = {}
    if 'network' in raw_config or 'compute' in raw_config or 'resources' in raw_config:
        return raw_config
    upgraded = copy.deepcopy(defaults)
    upgraded['compute']['instance_name'] = raw_config.get('instance_name', upgraded['compute']['instance_name'])
    upgraded['compute']['instance_type'] = raw_config.get('instance_type', upgraded['compute']['instance_type'])
    upgraded['compute']['image_id'] = raw_config.get('image_id', upgraded['compute']['image_id'])
    upgraded['compute']['system_disk_type'] = raw_config.get('system_disk_type', upgraded['compute']['system_disk_type'])
    upgraded['compute']['system_disk_size'] = raw_config.get('system_disk_size', upgraded['compute']['system_disk_size'])
    upgraded['compute']['public_bandwidth'] = raw_config.get('public_bandwidth', upgraded['compute']['public_bandwidth'])
    upgraded['compute']['instances'] = [{
        'instance_name': upgraded['compute']['instance_name'],
        'instance_type': upgraded['compute']['instance_type'],
        'image_id': upgraded['compute']['image_id'],
        'system_disk_type': upgraded['compute']['system_disk_type'],
        'system_disk_size': upgraded['compute']['system_disk_size'],
        'public_bandwidth': upgraded['compute']['public_bandwidth'],
    }]
    upgraded['network']['vpc_cidr'] = raw_config.get('vpc_cidr', upgraded['network']['vpc_cidr'])
    upgraded['network']['subnet_cidr'] = raw_config.get('subnet_cidr', upgraded['network']['subnet_cidr'])
    upgraded['network']['open_ingress_ports'] = raw_config.get('open_ingress_ports', upgraded['network']['open_ingress_ports'])
    return upgraded


def _deep_merge(base, override):
    if isinstance(base, dict) and isinstance(override, dict):
        merged = copy.deepcopy(base)
        for key, value in override.items():
            merged[key] = _deep_merge(merged[key], value) if key in merged else copy.deepcopy(value)
        return merged
    return copy.deepcopy(override)


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _first_non_empty(*values):
    for value in values:
        text = str(value or '').strip()
        if text:
            return text
    return ''


def _parse_network(value, key):
    try:
        return ipaddress.ip_network(str(value).strip(), strict=False)
    except ValueError as exc:
        raise ValidationError({'config': f'{key} 不是合法的 CIDR。'}) from exc


def _coerce_int(value, field, minimum=0):
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({'config': f'{field} 必须是整数。'}) from exc
    if number < minimum:
        raise ValidationError({'config': f'{field} 不能小于 {minimum}。'})
    return number


def _normalize_ports(value):
    if isinstance(value, str):
        items = [part for part in re.split(r'[\s,;]+', value.strip()) if part]
    elif isinstance(value, list):
        items = value
    else:
        raise ValidationError({'config': 'open_ingress_ports 只能是数组或逗号分隔字符串。'})
    ports = []
    for item in items:
        try:
            port = int(item)
        except (TypeError, ValueError) as exc:
            raise ValidationError({'config': f'无效端口: {item}'}) from exc
        if port < 1 or port > 65535:
            raise ValidationError({'config': f'端口必须在 1-65535 之间: {port}'})
        ports.append(port)
    if not ports:
        raise ValidationError({'config': '至少需要开放一个端口。'})
    return sorted(set(ports))


def _normalize_identifier(value, label):
    normalized = re.sub(r'[^a-zA-Z0-9_]+', '_', str(value).strip()).strip('_').lower()
    if not normalized:
        raise ValidationError({'config': f'{label} 不能为空。'})
    return normalized


def _normalize_bucket_name(value):
    bucket = re.sub(r'[^a-z0-9.-]+', '-', str(value or '').strip().lower()).strip('-.')
    if len(bucket) < 3 or len(bucket) > 63:
        raise ValidationError({'config': 'Bucket 名称长度必须在 3 到 63 之间。'})
    return bucket


def _hcl_string(value):
    escaped = str(value).replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'


def _hcl_list(values):
    return '[' + ', '.join(_hcl_string(item) if isinstance(item, str) else str(item) for item in values) + ']'


def _resource_suffix(index):
    return 'this' if index == 0 else f'this_{index + 1}'


def _build_versions_tf(provider_meta):
    return (
        'terraform {\n'
        '  required_version = ">= 1.5.0"\n\n'
        '  required_providers {\n'
        f'    {provider_meta["provider_name"]} = {{\n'
        f'      source  = "{provider_meta["provider_source"]}"\n'
        f'      version = "{provider_meta["provider_version"]}"\n'
        '    }\n'
        '  }\n'
        '}\n'
    )


def _build_provider_tf(payload):
    return (
        f'provider "{payload["provider_meta"]["provider_name"]}" {{\n'
        f'  region     = {_hcl_string(payload["region"])}\n'
        '  access_key = var.access_key\n'
        '  secret_key = var.secret_key\n'
        '}\n'
    )


def _build_variables_tf(payload):
    fields = [('access_key', 'Cloud access key'), ('secret_key', 'Cloud secret key'), ('instance_password', 'Compute administrator password')]
    if payload['config']['resources']['rds']['enabled']:
        fields.append(('db_password', 'RDS administrator password'))
    if payload['config']['resources']['redis']['enabled'] and payload['cloud_provider'] == 'huaweicloud':
        fields.append(('redis_password', 'Redis password'))
    lines = []
    for key, desc in fields:
        lines.extend([f'variable "{key}" {{', '  type        = string', f'  description = {_hcl_string(desc)}', '  sensitive   = true', '}', ''])
    return '\n'.join(lines).rstrip() + '\n'


def _build_main_tf(payload):
    return _build_aliyun_main_tf(payload) if payload['cloud_provider'] == 'aliyun' else _build_huaweicloud_main_tf(payload)


def _build_aliyun_main_tf(payload):
    config = payload['config']
    network = config['network']
    resources = config['resources']
    compute_instances = _get_compute_instances(config)
    bucket_items = _get_enabled_buckets(config)
    lines = [
        'locals {', f'  stack_name = {_hcl_string(payload["name"])}', f'  open_ingress_ports = {_hcl_list(network["open_ingress_ports"])}', '}', '',
        'resource "alicloud_vpc" "this" {', '  vpc_name   = "${local.stack_name}-vpc"', f'  cidr_block = {_hcl_string(network["vpc_cidr"])}', '}', '',
        'resource "alicloud_vswitch" "this" {', '  vpc_id       = alicloud_vpc.this.id', f'  zone_id      = {_hcl_string(payload["zone"])}', f'  cidr_block   = {_hcl_string(network["subnet_cidr"])}', '  vswitch_name = "${local.stack_name}-vsw"', '}', '',
        'resource "alicloud_security_group" "this" {', '  vpc_id              = alicloud_vpc.this.id', '  security_group_name = "${local.stack_name}-sg"', '  security_group_type = "normal"', '}', '',
        'resource "alicloud_security_group_rule" "ingress" {', '  count             = length(local.open_ingress_ports)', '  type              = "ingress"', '  ip_protocol       = "tcp"', '  nic_type          = "intranet"', '  policy            = "accept"', '  priority          = 1', '  port_range        = "${local.open_ingress_ports[count.index]}/${local.open_ingress_ports[count.index]}"', '  cidr_ip           = "0.0.0.0/0"', '  security_group_id = alicloud_security_group.this.id', '}', '',
    ]
    for index, compute in enumerate(compute_instances):
        resource_name = _resource_suffix(index)
        lines.extend([
            f'resource "alicloud_instance" "{resource_name}" {{',
            f'  availability_zone          = {_hcl_string(payload["zone"])}',
            f'  instance_name              = {_hcl_string(compute["instance_name"])}',
            f'  image_id                   = {_hcl_string(compute["image_id"])}',
            f'  instance_type              = {_hcl_string(compute["instance_type"])}',
            '  vswitch_id                 = alicloud_vswitch.this.id',
            '  security_groups            = [alicloud_security_group.this.id]',
            f'  internet_max_bandwidth_out = {compute["public_bandwidth"]}',
            f'  system_disk_category       = {_hcl_string(compute["system_disk_type"])}',
            f'  system_disk_size           = {compute["system_disk_size"]}',
            '  password                   = var.instance_password',
            '}',
            '',
        ])
    if resources['rds']['enabled']:
        rds = resources['rds']; lines.extend(['resource "alicloud_db_instance" "rds" {', f'  engine           = {_hcl_string(rds["engine"])}', f'  engine_version   = {_hcl_string(rds["engine_version"])}', f'  instance_type    = {_hcl_string(rds["instance_type"])}', f'  instance_storage = {rds["storage_gb"]}', f'  instance_name    = {_hcl_string(rds["name"])}', '  vswitch_id       = alicloud_vswitch.this.id', f'  security_ips     = {_hcl_list([network["vpc_cidr"]])}', f'  zone_id          = {_hcl_string(payload["zone"])}', '}', ''])
    if resources['redis']['enabled']:
        redis = resources['redis']; lines.extend(['resource "alicloud_kvstore_instance" "redis" {', f'  instance_name  = {_hcl_string(redis["name"])}', '  instance_type  = "Redis"', f'  engine_version = {_hcl_string(redis["engine_version"])}', f'  instance_class = {_hcl_string(redis["instance_class"])}', f'  zone_id        = {_hcl_string(payload["zone"])}', '  vswitch_id     = alicloud_vswitch.this.id', f'  security_ips   = {_hcl_list([network["vpc_cidr"]])}', '}', ''])
    if resources['load_balancer']['enabled']:
        lb = resources['load_balancer']; lines.extend(['resource "alicloud_slb_load_balancer" "lb" {', f'  load_balancer_name = {_hcl_string(lb["name"])}', f'  address_type       = {_hcl_string(lb["address_type"])}', '  vswitch_id         = alicloud_vswitch.this.id', f'  load_balancer_spec = {_hcl_string(lb["spec"])}', '}', ''])
    if resources['nat_gateway']['enabled']:
        nat = resources['nat_gateway']; lines.extend(['resource "alicloud_nat_gateway" "nat" {', '  vpc_id           = alicloud_vpc.this.id', '  vswitch_id       = alicloud_vswitch.this.id', '  nat_type         = "Enhanced"', '  payment_type     = "PayAsYouGo"', f'  nat_gateway_name = {_hcl_string(nat["name"])}', '}', '', 'resource "alicloud_eip_address" "nat" {', f'  bandwidth = {nat["bandwidth"]}', '}', '', 'resource "alicloud_eip_association" "nat" {', '  allocation_id = alicloud_eip_address.nat.id', '  instance_id   = alicloud_nat_gateway.nat.id', '}', ''])
    for index, bucket in enumerate(bucket_items):
        resource_name = 'bucket' if index == 0 else f'bucket_{index + 1}'
        lines.extend([
            f'resource "alicloud_oss_bucket" "{resource_name}" {{',
            f'  bucket        = {_hcl_string(bucket["bucket_name"])}',
            f'  acl           = {_hcl_string(bucket["acl"])}',
            f'  storage_class = {_hcl_string(bucket["storage_class"])}',
            '}',
            '',
        ])
    return '\n'.join(lines).rstrip() + '\n'


def _build_huaweicloud_main_tf(payload):
    config = payload['config']
    network = config['network']
    resources = config['resources']
    compute_instances = _get_compute_instances(config)
    bucket_items = _get_enabled_buckets(config)
    lines = [
        'resource "huaweicloud_vpc" "this" {', f'  name = {_hcl_string(payload["name"] + "-vpc")}', f'  cidr = {_hcl_string(network["vpc_cidr"])}', '}', '',
        'resource "huaweicloud_vpc_subnet" "this" {', f'  name              = {_hcl_string(payload["name"] + "-subnet")}', f'  cidr              = {_hcl_string(network["subnet_cidr"])}', f'  gateway_ip        = {_hcl_string(network["subnet_gateway"])}', '  vpc_id            = huaweicloud_vpc.this.id', f'  availability_zone = {_hcl_string(payload["zone"])}', '  dns_list          = ["100.125.1.250", "100.125.21.250"]', '}', '',
        'resource "huaweicloud_networking_secgroup" "this" {', f'  name        = {_hcl_string(payload["name"] + "-sg")}', '  description = "Managed by AI Ops Terraform generator"', '}', '',
        'resource "huaweicloud_networking_secgroup_rule" "ingress" {', f'  count             = {len(network["open_ingress_ports"])}', '  direction         = "ingress"', '  ethertype         = "IPv4"', '  protocol          = "tcp"', f'  port_range_min    = element({_hcl_list(network["open_ingress_ports"])}, count.index)', f'  port_range_max    = element({_hcl_list(network["open_ingress_ports"])}, count.index)', '  remote_ip_prefix  = "0.0.0.0/0"', '  security_group_id = huaweicloud_networking_secgroup.this.id', '}', '',
    ]
    for index, compute in enumerate(compute_instances):
        resource_name = _resource_suffix(index)
        lines.extend([
            f'resource "huaweicloud_compute_instance" "{resource_name}" {{',
            f'  name               = {_hcl_string(compute["instance_name"])}',
            f'  image_id           = {_hcl_string(compute["image_id"])}',
            f'  flavor_id          = {_hcl_string(compute["instance_type"])}',
            f'  availability_zone  = {_hcl_string(payload["zone"])}',
            '  security_group_ids = [huaweicloud_networking_secgroup.this.id]',
            '  admin_pass         = var.instance_password',
            f'  system_disk_type   = {_hcl_string(compute["system_disk_type"])}',
            f'  system_disk_size   = {compute["system_disk_size"]}',
            '',
            '  network {',
            '    uuid = huaweicloud_vpc_subnet.this.id',
            '  }',
            '}',
            '',
        ])
        if compute['public_bandwidth'] > 0:
            eip_name = 'this' if index == 0 else f'this_{index + 1}'
            lines.extend([
                f'resource "huaweicloud_vpc_eip" "{eip_name}" {{',
                '  publicip {',
                '    type = "5_bgp"',
                '  }',
                '',
                '  bandwidth {',
                f'    name        = {_hcl_string(payload["name"] + f"-eip-{index + 1:02d}")}',
                f'    size        = {compute["public_bandwidth"]}',
                '    share_type  = "PER"',
                '    charge_mode = "traffic"',
                '  }',
                '}',
                '',
                f'resource "huaweicloud_compute_eip_associate" "{eip_name}" {{',
                f'  public_ip   = huaweicloud_vpc_eip.{eip_name}.address',
                f'  instance_id = huaweicloud_compute_instance.{resource_name}.id',
                '}',
                '',
            ])
    if resources['rds']['enabled']:
        rds = resources['rds']; lines.extend(['resource "huaweicloud_rds_instance" "rds" {', f'  name              = {_hcl_string(rds["name"])}', f'  flavor            = {_hcl_string(rds["flavor"])}', f'  availability_zone = {_hcl_list([payload["zone"]])}', '  security_group_id = huaweicloud_networking_secgroup.this.id', '  vpc_id            = huaweicloud_vpc.this.id', '  subnet_id         = huaweicloud_vpc_subnet.this.id', '', '  db {', '    password = var.db_password', f'    type     = {_hcl_string(rds["engine"])}', f'    version  = {_hcl_string(rds["engine_version"])}', '    port     = 3306', '  }', '', '  volume {', f'    type = {_hcl_string(rds["volume_type"])}', f'    size = {rds["storage_gb"]}', '  }', '}', ''])
    if resources['redis']['enabled']:
        redis = resources['redis']; lines.extend(['resource "huaweicloud_dcs_instance" "redis" {', f'  name            = {_hcl_string(redis["name"])}', '  engine          = "Redis"', f'  engine_version  = {_hcl_string(redis["engine_version"])}', f'  capacity        = {redis["capacity"]}', f'  flavor          = {_hcl_string(redis["flavor"])}', f'  available_zones = {_hcl_list([payload["zone"]])}', '  vpc_id          = huaweicloud_vpc.this.id', '  subnet_id       = huaweicloud_vpc_subnet.this.id', '  password        = var.redis_password', '}', ''])
    if resources['load_balancer']['enabled']:
        lb = resources['load_balancer']; lines.extend(['resource "huaweicloud_elb_loadbalancer" "lb" {', f'  name          = {_hcl_string(lb["name"])}', f'  type          = {_hcl_string(lb["type"])}', f'  bandwidth     = {lb["bandwidth"]}', '  vip_subnet_id = huaweicloud_vpc_subnet.this.id', '}', ''])
    if resources['nat_gateway']['enabled']:
        nat = resources['nat_gateway']; lines.extend(['resource "huaweicloud_nat_gateway" "nat" {', f'  name                = {_hcl_string(nat["name"])}', f'  spec                = {_hcl_string(nat["spec"])}', '  router_id           = huaweicloud_vpc.this.id', '  internal_network_id = huaweicloud_vpc_subnet.this.id', '}', ''])
    for index, bucket in enumerate(bucket_items):
        resource_name = 'bucket' if index == 0 else f'bucket_{index + 1}'
        lines.extend([
            f'resource "huaweicloud_obs_bucket" "{resource_name}" {{',
            f'  bucket        = {_hcl_string(bucket["bucket_name"])}',
            f'  acl           = {_hcl_string(bucket["acl"])}',
            f'  storage_class = {_hcl_string(bucket["storage_class"])}',
            '}',
            '',
        ])
    return '\n'.join(lines).rstrip() + '\n'


def _build_outputs_tf(payload):
    provider = payload['cloud_provider']
    resources = payload['config']['resources']
    compute_instances = _get_compute_instances(payload['config'])
    bucket_items = _get_enabled_buckets(payload['config'])
    instance_id_exprs = []
    private_ip_exprs = []
    public_ip_exprs = []
    for index, instance in enumerate(compute_instances):
        resource_name = _resource_suffix(index)
        if provider == 'aliyun':
            instance_id_exprs.append(f'alicloud_instance.{resource_name}.id')
            private_ip_exprs.append(f'alicloud_instance.{resource_name}.private_ip')
            public_ip_exprs.append(f'try(alicloud_instance.{resource_name}.public_ip, null)')
        else:
            eip_name = 'this' if index == 0 else f'this_{index + 1}'
            instance_id_exprs.append(f'huaweicloud_compute_instance.{resource_name}.id')
            private_ip_exprs.append(f'huaweicloud_compute_instance.{resource_name}.access_ip_v4')
            public_ip_exprs.append(f'try(huaweicloud_vpc_eip.{eip_name}.address, null)' if instance['public_bandwidth'] > 0 else 'null')
    lines = [
        'output "instance_id" {', f'  value = {instance_id_exprs[0]}', '}', '',
        'output "instance_ids" {', f'  value = [{", ".join(instance_id_exprs)}]', '}', '',
        'output "private_ip" {', f'  value = {private_ip_exprs[0]}', '}', '',
        'output "private_ips" {', f'  value = [{", ".join(private_ip_exprs)}]', '}', '',
        'output "vpc_id" {', f'  value = {"alicloud_vpc.this.id" if provider == "aliyun" else "huaweicloud_vpc.this.id"}', '}', '',
        'output "subnet_id" {', f'  value = {"alicloud_vswitch.this.id" if provider == "aliyun" else "huaweicloud_vpc_subnet.this.id"}', '}', '',
        'output "public_ip" {', f'  value = {public_ip_exprs[0]}', '}', '',
        'output "public_ips" {', f'  value = [{", ".join(public_ip_exprs)}]', '}', '',
    ]
    optional_outputs = {'rds': ('rds_id', 'alicloud_db_instance.rds.id' if provider == 'aliyun' else 'huaweicloud_rds_instance.rds.id'), 'redis': ('redis_id', 'alicloud_kvstore_instance.redis.id' if provider == 'aliyun' else 'huaweicloud_dcs_instance.redis.id'), 'load_balancer': ('load_balancer_id', 'alicloud_slb_load_balancer.lb.id' if provider == 'aliyun' else 'huaweicloud_elb_loadbalancer.lb.id'), 'nat_gateway': ('nat_gateway_id', 'alicloud_nat_gateway.nat.id' if provider == 'aliyun' else 'huaweicloud_nat_gateway.nat.id')}
    for key, (name, expr) in optional_outputs.items():
        if resources[key]['enabled']:
            lines.extend([f'output "{name}" {{', f'  value = {expr}', '}', ''])
    if bucket_items:
        bucket_exprs = [f'{"alicloud_oss_bucket" if provider == "aliyun" else "huaweicloud_obs_bucket"}.{"bucket" if index == 0 else f"bucket_{index + 1}"}.bucket' for index, _ in enumerate(bucket_items)]
        lines.extend(['output "bucket_name" {', f'  value = {bucket_exprs[0]}', '}', '', 'output "bucket_names" {', f'  value = [{", ".join(bucket_exprs)}]', '}', ''])
    return '\n'.join(lines).rstrip() + '\n'


def _build_tfvars(payload, secrets=None):
    values = OrderedDict([('access_key', (secrets or {}).get('access_key', 'REPLACE_ME')), ('secret_key', (secrets or {}).get('secret_key', 'REPLACE_ME')), ('instance_password', (secrets or {}).get('instance_password', 'REPLACE_ME'))])
    if payload['config']['resources']['rds']['enabled']:
        values['db_password'] = (secrets or {}).get('db_password', 'REPLACE_ME')
    if payload['config']['resources']['redis']['enabled'] and payload['cloud_provider'] == 'huaweicloud':
        values['redis_password'] = (secrets or {}).get('redis_password', 'REPLACE_ME')
    return '\n'.join(f'{key} = {_hcl_string(value)}' for key, value in values.items()) + '\n'


def _build_readme(payload, has_secret_tfvars):
    config = payload['config']
    compute_instances = _get_compute_instances(config)
    summary_lines = [
        f'- 云厂商: {payload["provider_meta"]["label"]}',
        f'- 区域 / 可用区: `{payload["region"]}` / `{payload["zone"]}`',
        f'- 系统 / 环境: `{config["metadata"].get("business_line") or "default"}` / `{config["metadata"]["environment"]}`',
        f'- VPC / 子网: `{config["network"]["vpc_cidr"]}` / `{config["network"]["subnet_cidr"]}`',
        f'- 服务器数量: `{len(compute_instances)}`',
    ]
    for index, instance in enumerate(compute_instances, start=1):
        summary_lines.append(f'- 服务器 {index}: `{instance["instance_name"]}` ({instance["instance_type"]})')
    for item in payload['resource_inventory']:
        if item['key'] not in {'vpc', 'subnet', 'security_group'} and not item['key'].startswith('compute') and not item['key'].startswith('eip'):
            summary_lines.append(f'- 扩展资源: `{item["label"]}` -> `{item["name"]}`')
    if payload['resource_relationships']:
        summary_lines.append(f'- 资源关联数: `{len(payload["resource_relationships"])}`')
        for relation in payload['resource_relationships']:
            summary_lines.append(f'- 关联关系: `{relation["source_name"]}` {relation["relation_type"]} `{relation["target_name"]}`')
    usage = ['1. 安装 Terraform 1.5+。', '2. 执行 `terraform init`。', '3. 根据需要修改 `terraform.tfvars` 中的敏感信息。' if has_secret_tfvars else '3. 将 `terraform.tfvars.example` 复制为 `terraform.tfvars` 并填写敏感信息。', '4. 执行 `terraform plan`，确认无误后执行 `terraform apply`。']
    return '\n'.join([f'# {payload["display_name"] or payload["name"]}', '', payload['provider_meta']['description'], '', '## 资源清单', '', *summary_lines, '', '## 使用方式', '', *usage, '', '## 说明', '', '- 该工程由 AI Ops 自动生成。', '- 敏感凭证不会持久化到 AI Ops 数据库。', '- 如需更复杂的路由、监听器、白名单或参数组，请在生成文件基础上继续扩展。', ''])
