from django.core.management.base import BaseCommand

from multicloud.models import CloudAsset, CloudCredential, CloudEnvironment, CloudSyncTask
from multicloud.services import sync_environment_inventory, sync_environment_to_cmdb


DEMO_CREDENTIALS = [
    {'provider': 'aliyun', 'name': '阿里云-交易系统生产主账号', 'account_id': '100001', 'account_name': 'trade-prod', 'auth_mode': 'demo', 'access_key_id': 'aliyun-demo-ak', 'access_key_secret': 'aliyun-demo-sk', 'default_region': 'cn-hangzhou', 'owner': 'SRE-张楠', 'description': '参考 AutoOps 的云账号 / 云主机纳管思路，提供交易系统生产账号 Demo。', 'tags': {'team': 'trade'}, 'is_enabled': True, 'demo_mode': True},
    {'provider': 'tencent', 'name': '腾讯云-游戏测试账号', 'account_id': '200002', 'account_name': 'game-test', 'auth_mode': 'demo', 'access_key_id': 'tencent-demo-ak', 'access_key_secret': 'tencent-demo-sk', 'default_region': 'ap-guangzhou', 'owner': '平台测试-周遥', 'description': '用于测试环境和灰度资源纳管。', 'tags': {'team': 'game'}, 'is_enabled': True, 'demo_mode': True},
    {'provider': 'huawei', 'name': '华为云-政企共享账号', 'account_id': '300003', 'account_name': 'gov-shared', 'auth_mode': 'demo', 'access_key_id': 'huawei-demo-ak', 'access_key_secret': 'huawei-demo-sk', 'default_region': 'cn-north-4', 'owner': '政企云-刘哲', 'description': '用于共享中台、容灾与网络治理演示。', 'tags': {'team': 'shared'}, 'is_enabled': True, 'demo_mode': True},
]

DEMO_ENVIRONMENTS = [
    {'credential_name': '阿里云-交易系统生产主账号', 'name': '订单中心生产', 'code': 'trade-prod-hz', 'business_line': '交易系统', 'environment_type': 'prod', 'region': 'cn-hangzhou', 'zone': 'cn-hangzhou-h', 'vpc_name': 'vpc-trade-prod', 'network_cidr': '10.10.0.0/16', 'owner': '交易系统 SRE', 'description': '订单、支付与网关核心生产环境。', 'tags': {'app': 'order-center', 'criticality': 'p0'}},
    {'credential_name': '阿里云-交易系统生产主账号', 'name': '数据平台共享', 'code': 'data-shared-hz', 'business_line': '数据平台', 'environment_type': 'shared', 'region': 'cn-shanghai', 'zone': 'cn-shanghai-a', 'vpc_name': 'vpc-data-shared', 'network_cidr': '10.40.0.0/16', 'owner': '数据平台', 'description': '共享 Kafka / Flink / Airflow 配套环境。', 'tags': {'app': 'data-platform', 'criticality': 'p1'}},
    {'credential_name': '腾讯云-游戏测试账号', 'name': '会员中心测试', 'code': 'member-test-gz', 'business_line': '会员', 'environment_type': 'test', 'region': 'ap-guangzhou', 'zone': 'ap-guangzhou-2', 'vpc_name': 'vpc-member-test', 'network_cidr': '10.20.0.0/16', 'owner': '会员测试团队', 'description': '压测、回归和预发布环境。', 'tags': {'app': 'member-center', 'criticality': 'p2'}},
    {'credential_name': '华为云-政企共享账号', 'name': 'AI 能力开发', 'code': 'ai-dev-bj4', 'business_line': 'AI 平台', 'environment_type': 'dev', 'region': 'cn-north-4', 'zone': 'cn-north-4a', 'vpc_name': 'vpc-ai-dev', 'network_cidr': '10.30.0.0/16', 'owner': 'AI 开发组', 'description': '模型训练、特征服务和开发沙箱。', 'tags': {'app': 'ai-platform', 'criticality': 'p2'}},
]


class Command(BaseCommand):
    help = '生成多云环境管理 Demo 数据'

    def handle(self, *args, **options):
        self.stdout.write('清理旧的多云 Demo 数据...')
        CloudSyncTask.objects.all().delete()
        CloudAsset.objects.all().delete()
        CloudEnvironment.objects.all().delete()
        CloudCredential.objects.all().delete()

        self.stdout.write('创建云账号...')
        credential_map = {item['name']: CloudCredential.objects.create(created_by='seed', updated_by='seed', **item) for item in DEMO_CREDENTIALS}

        self.stdout.write('创建云环境...')
        environments = []
        for item in DEMO_ENVIRONMENTS:
            payload = dict(item)
            credential_name = payload.pop('credential_name')
            environments.append(CloudEnvironment.objects.create(credential=credential_map[credential_name], created_by='seed', updated_by='seed', **payload))

        self.stdout.write('同步多云资源 Demo...')
        for environment in environments:
            sync_environment_inventory(environment, operator='seed')

        self.stdout.write('同步部分环境到 CMDB...')
        for environment in environments[:2]:
            sync_environment_to_cmdb(environment, operator='seed')

        self.stdout.write(self.style.SUCCESS(f'多云 Demo 已生成：{CloudCredential.objects.count()} 个账号，{CloudEnvironment.objects.count()} 个环境，{CloudAsset.objects.count()} 个资源。'))
