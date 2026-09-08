from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from cmdb.models import ConfigItem
from multicloud.models import CloudAsset, CloudCredential, CloudEnvironment
from multicloud.services import sync_environment_inventory


class MultiCloudTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_superuser('multicloud-admin', 'multicloud@example.com', 'Admin@123456')
        self.client.force_authenticate(self.user)
        self.credential = CloudCredential.objects.create(
            provider='aliyun',
            name='aliyun-demo',
            account_id='100001',
            account_name='trade-prod',
            auth_mode='demo',
            access_key_id='demo-ak',
            access_key_secret='demo-sk',
            default_region='cn-hangzhou',
            owner='SRE',
            demo_mode=True,
            created_by='test',
            updated_by='test',
        )
        self.environment = CloudEnvironment.objects.create(
            credential=self.credential,
            name='订单中心生产',
            code='trade-prod-hz',
            business_line='交易系统',
            environment_type='prod',
            region='cn-hangzhou',
            zone='cn-hangzhou-h',
            vpc_name='vpc-trade-prod',
            network_cidr='10.10.0.0/16',
            owner='交易系统 SRE',
            created_by='test',
            updated_by='test',
        )

    def test_catalog_endpoint_returns_supported_providers(self):
        response = self.client.get('/api/multicloud/catalog/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()['providers']
        self.assertIn('aliyun', payload)
        self.assertIn('resource_types', payload['aws'])
        self.assertIn('sdk', payload['aws'])

    def test_environment_sync_creates_demo_assets(self):
        response = self.client.post(f'/api/multicloud/environments/{self.environment.id}/sync/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()['environment']['asset_count'], 6)
        self.assertTrue(CloudAsset.objects.filter(environment=self.environment, resource_type='ecs').exists())

    def test_credential_sync_all_runs_for_related_environments(self):
        CloudEnvironment.objects.create(
            credential=self.credential,
            name='订单中心共享',
            code='trade-shared-hz',
            business_line='交易系统',
            environment_type='shared',
            region='cn-shanghai',
            owner='平台',
            created_by='test',
            updated_by='test',
        )
        response = self.client.post(f'/api/multicloud/credentials/{self.credential.id}/sync_all/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result']['count'], 2)

    def test_overview_endpoint_aggregates_assets_and_costs(self):
        sync_environment_inventory(self.environment, operator='test')
        response = self.client.get('/api/multicloud/overview/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['stats']['credential_count'], 1)
        self.assertGreaterEqual(payload['stats']['asset_count'], 6)
        self.assertTrue(payload['recommendations'])
        self.assertTrue(payload['cost_trend']['series'])

    def test_sync_cmdb_creates_cmdb_items(self):
        sync_environment_inventory(self.environment, operator='test')
        response = self.client.post(f'/api/multicloud/environments/{self.environment.id}/sync_cmdb/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertGreater(ConfigItem.objects.count(), 0)
        self.assertTrue(ConfigItem.objects.filter(attributes__cmdb_source='multicloud').exists())

    def test_topology_endpoint_returns_graph_payload(self):
        sync_environment_inventory(self.environment, operator='test')
        response = self.client.get('/api/multicloud/topology/', {'provider': 'aliyun'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreater(payload['stats']['node_count'], 0)
        self.assertTrue(any(node['id'].startswith('credential-') for node in payload['nodes']))
        self.assertTrue(any(edge['value'] == '账号归属' for edge in payload['edges']))

    def test_cost_trend_endpoint_supports_grouping(self):
        sync_environment_inventory(self.environment, operator='test')
        response = self.client.get('/api/multicloud/cost-trend/', {'group_by': 'resource_type', 'provider': 'aliyun'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['group_by'], 'resource_type')
        self.assertEqual(len(payload['labels']), 6)
        self.assertTrue(payload['series'])

    def test_batch_action_can_disable_credentials(self):
        response = self.client.post(
            '/api/multicloud/batch-actions/',
            {'scope': 'credentials', 'action': 'disable', 'ids': [self.credential.id]},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.credential.refresh_from_db()
        self.assertFalse(self.credential.is_enabled)

    def test_batch_action_can_mark_assets_as_drift(self):
        sync_environment_inventory(self.environment, operator='test')
        asset = CloudAsset.objects.filter(environment=self.environment).first()
        response = self.client.post(
            '/api/multicloud/batch-actions/',
            {'scope': 'assets', 'action': 'mark_drift', 'ids': [asset.id]},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        asset.refresh_from_db()
        self.assertEqual(asset.sync_state, 'drift')

    def test_real_sdk_without_valid_credentials_returns_non_healthy_status(self):
        self.credential.demo_mode = False
        self.credential.save(update_fields=['demo_mode'])
        response = self.client.post(f'/api/multicloud/credentials/{self.credential.id}/test_connection/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(payload['status'], {'warning', 'error'})
        self.assertNotEqual(payload['status'], 'healthy')

    @patch('multicloud.services.get_cloud_adapter')
    def test_real_sdk_inventory_sync_uses_adapter_rows(self, mocked_get_adapter):
        self.credential.provider = 'aws'
        self.credential.demo_mode = False
        self.credential.default_region = 'ap-southeast-1'
        self.credential.save(update_fields=['provider', 'demo_mode', 'default_region'])

        class FakeAdapter:
            def __init__(self, credential):
                self.credential = credential

            def capability(self):
                return {'provider': 'aws', 'installed': True, 'supports_inventory': True}

            def fetch_inventory(self, environment):
                return [
                    {
                        'name': 'aws-live-ecs-01',
                        'provider': 'aws',
                        'resource_type': 'ecs',
                        'resource_id': 'i-live-001',
                        'region': 'ap-southeast-1',
                        'zone': 'ap-southeast-1a',
                        'status': 'running',
                        'charge_type': 'on_demand',
                        'private_ip': '10.10.1.10',
                        'public_ip': '203.0.113.54',
                        'vpc_name': 'vpc-live',
                        'spec': 't3.large',
                        'cpu': 2,
                        'memory_gb': '8',
                        'disk_gb': '120',
                        'monthly_cost': '888',
                        'risk_level': 'normal',
                        'sync_state': 'synced',
                        'tags': {'Name': 'aws-live-ecs-01'},
                        'metadata': {'source': 'sdk'},
                    }
                ]

        mocked_get_adapter.side_effect = lambda credential: FakeAdapter(credential)
        response = self.client.post(f'/api/multicloud/environments/{self.environment.id}/sync/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(CloudAsset.objects.filter(environment=self.environment, resource_id='i-live-001').exists())
        self.environment.refresh_from_db()
        self.assertEqual(self.environment.summary['sync_mode'], 'sdk')
