import importlib
import importlib.util
import json
from datetime import date
from decimal import Decimal


class CloudAdapterError(RuntimeError):
    pass


def _has_module(module_name):
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_decimal(value, default='0'):
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _tag_map(pairs):
    rows = {}
    for item in pairs or []:
        key = item.get('Key') or item.get('key')
        value = item.get('Value') or item.get('value')
        if key:
            rows[key] = value
    return rows


class BaseCloudAdapter:
    provider = ''
    provider_label = ''
    required_modules = ()
    supports_inventory = False
    supports_costs = False

    def __init__(self, credential):
        self.credential = credential

    @classmethod
    def dependency_status(cls):
        modules = {module: _has_module(module) for module in cls.required_modules}
        installed = all(modules.values()) if modules else False
        return {
            'provider': cls.provider,
            'provider_label': cls.provider_label or cls.provider,
            'installed': installed,
            'required_modules': list(cls.required_modules),
            'modules': modules,
            'supports_inventory': cls.supports_inventory,
            'supports_costs': cls.supports_costs,
        }

    def capability(self):
        return self.dependency_status()

    def default_region(self, fallback=''):
        return self.credential.default_region or fallback

    def unavailable_error(self):
        required = ', '.join(self.required_modules) or 'provider sdk'
        raise CloudAdapterError(f'{self.provider_label} SDK is unavailable. Install: {required}')

    def asset(self, environment, name, resource_type, resource_id, **kwargs):
        return {
            'name': name,
            'provider': environment.credential.provider,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'region': kwargs.get('region') or environment.region or self.default_region(),
            'zone': kwargs.get('zone') or environment.zone or '',
            'status': kwargs.get('status', 'running'),
            'charge_type': kwargs.get('charge_type', 'on_demand'),
            'private_ip': kwargs.get('private_ip', ''),
            'public_ip': kwargs.get('public_ip', ''),
            'vpc_name': kwargs.get('vpc_name') or environment.vpc_name or '',
            'spec': kwargs.get('spec', ''),
            'cpu': _safe_int(kwargs.get('cpu', 0)),
            'memory_gb': _safe_decimal(kwargs.get('memory_gb', '0')),
            'disk_gb': _safe_decimal(kwargs.get('disk_gb', '0')),
            'monthly_cost': _safe_decimal(kwargs.get('monthly_cost', '0')),
            'risk_level': kwargs.get('risk_level', 'normal'),
            'sync_state': kwargs.get('sync_state', 'synced'),
            'tags': kwargs.get('tags') or {},
            'metadata': kwargs.get('metadata') or {},
        }

    def test_connection(self):
        self.unavailable_error()

    def fetch_inventory(self, environment):
        self.unavailable_error()

    def fetch_cost_series(self, months=6):
        return None


class AwsCloudAdapter(BaseCloudAdapter):
    provider = 'aws'
    provider_label = 'AWS'
    required_modules = ('boto3',)
    supports_inventory = True
    supports_costs = True

    def _session(self):
        if not self.capability()['installed']:
            self.unavailable_error()
        boto3 = importlib.import_module('boto3')
        session_kwargs = {}
        if self.credential.access_key_id:
            session_kwargs['aws_access_key_id'] = self.credential.access_key_id
        if self.credential.access_key_secret:
            session_kwargs['aws_secret_access_key'] = self.credential.access_key_secret
        region_name = self.default_region('ap-southeast-1')
        base_session = boto3.session.Session(region_name=region_name, **session_kwargs)
        if not self.credential.role_arn:
            return base_session
        params = {'RoleArn': self.credential.role_arn, 'RoleSessionName': f'sxdevops-{self.credential.id}'}
        if self.credential.external_id:
            params['ExternalId'] = self.credential.external_id
        creds = base_session.client('sts', region_name=region_name).assume_role(**params)['Credentials']
        return boto3.session.Session(
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken'],
            region_name=region_name,
        )

    def test_connection(self):
        session = self._session()
        region = self.default_region('ap-southeast-1')
        identity = session.client('sts', region_name=region).get_caller_identity()
        return {
            'success': True,
            'status': 'healthy',
            'message': f'AWS STS connectivity verified for account {identity.get("Account", "-")}.',
            'region': region,
            'demo_mode': False,
            'sdk_mode': 'aws-boto3',
            'account': identity.get('Account', ''),
            'arn': identity.get('Arn', ''),
        }

    def fetch_inventory(self, environment):
        session = self._session()
        region = environment.region or self.default_region('ap-southeast-1')
        assets = []
        ec2 = session.client('ec2', region_name=region)
        for reservation in ec2.describe_instances().get('Reservations', []):
            for instance in reservation.get('Instances', []):
                tags = _tag_map(instance.get('Tags'))
                name = tags.get('Name') or instance.get('InstanceId')
                assets.append(self.asset(environment, name, 'ecs', instance.get('InstanceId'), region=region, zone=instance.get('Placement', {}).get('AvailabilityZone', ''), status='running' if instance.get('State', {}).get('Name') == 'running' else 'stopped', charge_type=instance.get('InstanceLifecycle') or 'on_demand', private_ip=instance.get('PrivateIpAddress', ''), public_ip=instance.get('PublicIpAddress', ''), vpc_name=instance.get('VpcId', ''), spec=instance.get('InstanceType', ''), tags=tags))
        return assets

    def fetch_cost_series(self, months=6):
        session = self._session()
        client = session.client('ce', region_name='us-east-1')
        end = date.today().replace(day=1)
        start_year = end.year
        start_month = end.month - (months - 1)
        while start_month <= 0:
            start_year -= 1
            start_month += 12
        start = date(start_year, start_month, 1)
        response = client.get_cost_and_usage(TimePeriod={'Start': start.isoformat(), 'End': end.isoformat()}, Granularity='MONTHLY', Metrics=['UnblendedCost'])
        labels, values = [], []
        for row in response.get('ResultsByTime', []):
            labels.append(row.get('TimePeriod', {}).get('Start', '')[:7])
            values.append(float(row.get('Total', {}).get('UnblendedCost', {}).get('Amount', '0')))
        return {'labels': labels, 'values': values, 'unit': 'USD'}


class AliyunCloudAdapter(BaseCloudAdapter):
    provider = 'aliyun'
    provider_label = 'Aliyun'
    required_modules = ('aliyunsdkcore', 'aliyunsdkecs')
    supports_inventory = True

    def _client(self, region=''):
        if not self.capability()['installed']:
            self.unavailable_error()
        client_module = importlib.import_module('aliyunsdkcore.client')
        return client_module.AcsClient(self.credential.access_key_id, self.credential.access_key_secret, region or self.default_region('cn-hangzhou'))

    def test_connection(self):
        request_module = importlib.import_module('aliyunsdkecs.request.v20140526.DescribeRegionsRequest')
        request = request_module.DescribeRegionsRequest()
        request.set_accept_format('json')
        response = json.loads(self._client().do_action_with_exception(request))
        count = len((response.get('Regions') or {}).get('Region', []))
        return {
            'success': True,
            'status': 'healthy',
            'message': f'Aliyun ECS connectivity verified, {count} regions visible.',
            'region': self.default_region('cn-hangzhou'),
            'demo_mode': False,
            'sdk_mode': 'aliyun-python-sdk',
            'count': count,
        }

    def fetch_inventory(self, environment):
        request_module = importlib.import_module('aliyunsdkecs.request.v20140526.DescribeInstancesRequest')
        request = request_module.DescribeInstancesRequest()
        request.set_accept_format('json')
        response = json.loads(self._client(environment.region or self.default_region('cn-hangzhou')).do_action_with_exception(request))
        assets = []
        for row in ((response.get('Instances') or {}).get('Instance') or []):
            tags = {}
            for tag in (((row.get('Tags') or {}).get('Tag') or [])):
                if tag.get('TagKey'):
                    tags[tag['TagKey']] = tag.get('TagValue', '')
            private_ips = ((row.get('VpcAttributes') or {}).get('PrivateIpAddress') or {}).get('IpAddress') or []
            public_ips = ((row.get('PublicIpAddress') or {}).get('IpAddress') or [])
            assets.append(self.asset(environment, row.get('InstanceName') or row.get('InstanceId'), 'ecs', row.get('InstanceId'), region=row.get('RegionId') or environment.region, zone=row.get('ZoneId', ''), status='running' if row.get('Status') == 'Running' else 'stopped', charge_type=row.get('InstanceChargeType', ''), private_ip=private_ips[0] if private_ips else '', public_ip=public_ips[0] if public_ips else '', vpc_name=(row.get('VpcAttributes') or {}).get('VpcId', ''), spec=row.get('InstanceType', ''), cpu=row.get('Cpu', 0), memory_gb=row.get('Memory', 0), tags=tags))
        return assets


class TencentCloudAdapter(BaseCloudAdapter):
    provider = 'tencent'
    provider_label = 'Tencent Cloud'
    required_modules = ('tencentcloud',)
    supports_inventory = True

    def test_connection(self):
        if not self.capability()['installed']:
            self.unavailable_error()
        credential_module = importlib.import_module('tencentcloud.common.credential')
        profile_module = importlib.import_module('tencentcloud.common.profile.client_profile')
        http_module = importlib.import_module('tencentcloud.common.profile.http_profile')
        client_module = importlib.import_module('tencentcloud.sts.v20180813.sts_client')
        models_module = importlib.import_module('tencentcloud.sts.v20180813.models')
        cred = credential_module.Credential(self.credential.access_key_id, self.credential.access_key_secret)
        http_profile = http_module.HttpProfile()
        http_profile.endpoint = 'sts.tencentcloudapi.com'
        client_profile = profile_module.ClientProfile()
        client_profile.httpProfile = http_profile
        client = client_module.StsClient(cred, self.default_region('ap-guangzhou'), client_profile)
        payload = json.loads(client.GetCallerIdentity(models_module.GetCallerIdentityRequest()).to_json_string())
        return {
            'success': True,
            'status': 'healthy',
            'message': f'TencentCloud STS connectivity verified for UIN {payload.get("UserId", "-")}.',
            'region': self.default_region('ap-guangzhou'),
            'demo_mode': False,
            'sdk_mode': 'tencentcloud-sdk-python',
            'account': payload.get('AccountId', ''),
        }

    def fetch_inventory(self, environment):
        if not self.capability()['installed']:
            self.unavailable_error()
        credential_module = importlib.import_module('tencentcloud.common.credential')
        profile_module = importlib.import_module('tencentcloud.common.profile.client_profile')
        http_module = importlib.import_module('tencentcloud.common.profile.http_profile')
        client_module = importlib.import_module('tencentcloud.cvm.v20170312.cvm_client')
        models_module = importlib.import_module('tencentcloud.cvm.v20170312.models')
        cred = credential_module.Credential(self.credential.access_key_id, self.credential.access_key_secret)
        http_profile = http_module.HttpProfile()
        http_profile.endpoint = 'cvm.tencentcloudapi.com'
        client_profile = profile_module.ClientProfile()
        client_profile.httpProfile = http_profile
        client = client_module.CvmClient(cred, environment.region or self.default_region('ap-guangzhou'), client_profile)
        payload = json.loads(client.DescribeInstances(models_module.DescribeInstancesRequest()).to_json_string())
        assets = []
        for row in payload.get('InstanceSet', []):
            private_ips = row.get('PrivateIpAddresses') or []
            public_ips = row.get('PublicIpAddresses') or []
            assets.append(self.asset(environment, row.get('InstanceName') or row.get('InstanceId'), 'ecs', row.get('InstanceId'), region=environment.region or self.default_region('ap-guangzhou'), zone=row.get('Placement', {}).get('Zone', ''), status='running' if row.get('InstanceState') == 'RUNNING' else 'stopped', charge_type=row.get('InstanceChargeType', ''), private_ip=private_ips[0] if private_ips else '', public_ip=public_ips[0] if public_ips else '', vpc_name=row.get('VirtualPrivateCloud', {}).get('VpcId', ''), spec=row.get('InstanceType', '')))
        return assets


class HuaweiCloudAdapter(BaseCloudAdapter):
    provider = 'huawei'
    provider_label = 'Huawei Cloud'
    required_modules = ('huaweicloudsdkcore', 'huaweicloudsdkecs')
    supports_inventory = True

    def _client(self, region=''):
        if not self.capability()['installed']:
            self.unavailable_error()
        if not self.credential.project_id:
            raise CloudAdapterError('Huawei Cloud requires project_id for AK/SK API access.')
        credentials_module = importlib.import_module('huaweicloudsdkcore.auth.credentials')
        ecs_module = importlib.import_module('huaweicloudsdkecs.v2')
        region_module = importlib.import_module('huaweicloudsdkecs.v2.region.ecs_region')
        credentials = credentials_module.BasicCredentials(self.credential.access_key_id, self.credential.access_key_secret, self.credential.project_id)
        return ecs_module.EcsClient.new_builder().with_credentials(credentials).with_region(region_module.EcsRegion.value_of(region or self.default_region('cn-north-4'))).build()

    def test_connection(self):
        ecs_module = importlib.import_module('huaweicloudsdkecs.v2')
        response = self._client().list_servers_details(ecs_module.ListServersDetailsRequest())
        count = len(getattr(response, 'servers', []) or [])
        return {
            'success': True,
            'status': 'healthy',
            'message': f'Huawei Cloud ECS connectivity verified, {count} servers visible.',
            'region': self.default_region('cn-north-4'),
            'demo_mode': False,
            'sdk_mode': 'huaweicloud-python-sdk',
            'count': count,
        }

    def fetch_inventory(self, environment):
        ecs_module = importlib.import_module('huaweicloudsdkecs.v2')
        response = self._client(environment.region or self.default_region('cn-north-4')).list_servers_details(ecs_module.ListServersDetailsRequest())
        assets = []
        for row in getattr(response, 'servers', []) or []:
            private_ip = ''
            public_ip = ''
            for address_list in (getattr(row, 'addresses', {}) or {}).values():
                for address in address_list or []:
                    addr = getattr(address, 'addr', '') or ''
                    ip_type = getattr(address, 'os_ext_ip_stype', '') or ''
                    if ip_type == 'floating' and not public_ip:
                        public_ip = addr
                    elif not private_ip:
                        private_ip = addr
            tags = {}
            for tag in getattr(row, 'tags', []) or []:
                if isinstance(tag, str) and '=' in tag:
                    key, value = tag.split('=', 1)
                    tags[key] = value
            assets.append(self.asset(environment, getattr(row, 'name', '') or getattr(row, 'id', ''), 'ecs', getattr(row, 'id', ''), region=environment.region or self.default_region('cn-north-4'), zone=getattr(row, 'os_ext_a_zavailability_zone', '') or '', status='running' if getattr(row, 'status', '') == 'ACTIVE' else 'stopped', private_ip=private_ip, public_ip=public_ip, spec=getattr(getattr(row, 'flavor', None), 'id', '') or '', tags=tags, metadata={'host_status': getattr(row, 'host_status', ''), 'description': getattr(row, 'description', ''), 'enterprise_project_id': getattr(row, 'enterprise_project_id', '')}))
        return assets


class PlaceholderCloudAdapter(BaseCloudAdapter):
    def unavailable_error(self):
        raise CloudAdapterError(f'{self.provider_label} live SDK integration is not installed in this environment.')


class BaiduCloudAdapter(PlaceholderCloudAdapter):
    provider = 'baidu'
    provider_label = 'Baidu AI Cloud'
    required_modules = ('baidubce',)


ADAPTERS = {
    'aliyun': AliyunCloudAdapter,
    'tencent': TencentCloudAdapter,
    'huawei': HuaweiCloudAdapter,
    'baidu': BaiduCloudAdapter,
    'aws': AwsCloudAdapter,
}


def get_cloud_adapter(credential):
    adapter_class = ADAPTERS.get(credential.provider)
    if not adapter_class:
        return None
    return adapter_class(credential)


def get_provider_sdk_capabilities():
    return {provider: adapter.dependency_status() for provider, adapter in ADAPTERS.items()}
