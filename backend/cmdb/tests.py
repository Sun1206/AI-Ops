import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from rbac.models import PermissionDefinition, Role
from rbac.services import ensure_builtin_rbac
from ops.models import Host

from .models import CIType, CIRelation, ConfigItem, CostRecord, ResourceNode, ResourceRequest


class AuthenticatedTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_superuser('cmdb-admin', 'cmdb@example.com', 'Admin@123456')
        self.client.force_login(self.user)


class CmdbCostAnalysisTests(AuthenticatedTestCase):
    def setUp(self):
        super().setUp()
        self.current_month = timezone.now().strftime('%Y-%m')
        self.previous_month = (
            timezone.now().replace(day=1) - timezone.timedelta(days=1)
        ).strftime('%Y-%m')

        host_type = CIType.objects.create(name='Host')
        db_type = CIType.objects.create(name='Database')

        self.prod_ci = ConfigItem.objects.create(
            name='prod-db-01',
            ci_type=db_type,
            business_line='core',
            environment='prod',
            status='active',
            attributes={'monthly_cost': 1200, 'cpu': 16, 'memory_gb': 32},
        )
        self.test_ci = ConfigItem.objects.create(
            name='test-host-01',
            ci_type=host_type,
            business_line='core',
            environment='test',
            status='active',
            attributes={'monthly_cost': 600, 'cpu': 8, 'memory_gb': 16},
        )
        self.idle_ci = ConfigItem.objects.create(
            name='idle-host-01',
            ci_type=host_type,
            business_line='shared',
            environment='prod',
            status='idle',
            attributes={'monthly_cost': 300, 'cpu': 4, 'memory_gb': 8},
        )
        CostRecord.objects.create(
            ci=self.prod_ci,
            month=self.previous_month,
            amount=Decimal('1000.00'),
            provider='history',
        )

    def test_cost_report_uses_current_month_fallbacks_without_writing_cost_records(self):
        response = self.client.get('/api/cmdb/cost/report/', {'month': self.current_month})

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload['month'], self.current_month)
        self.assertEqual(payload['total_monthly_cost'], 2100.0)
        self.assertEqual(payload['top_cost_items'][0]['name'], 'prod-db-01')
        self.assertEqual(payload['by_business'][0]['business_line'], 'core')
        self.assertEqual(payload['by_business'][0]['total_cost'], 1800.0)
        self.assertEqual(payload['by_environment'][0]['environment'], 'prod')
        self.assertEqual(payload['total_potential_saving'], 870.0)
        self.assertEqual(payload['optimized_monthly_cost'], 1230.0)
        self.assertEqual(payload['optimization_preview']['suggestion_count'], 3)
        self.assertTrue(
            any(point['period'] == self.current_month for point in payload['cost_trend'])
        )
        self.assertEqual(
            CostRecord.objects.filter(month=self.current_month).count(),
            0,
        )

    def test_cost_report_supports_historical_months_without_resync(self):
        response = self.client.get('/api/cmdb/cost/report/', {'month': self.previous_month})

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload['total_monthly_cost'], 1000.0)
        self.assertEqual(len(payload['top_cost_items']), 1)
        self.assertEqual(payload['top_cost_items'][0]['name'], 'prod-db-01')
        self.assertEqual(payload['optimization_preview']['suggestion_count'], 1)

    def test_optimization_returns_actionable_suggestions(self):
        response = self.client.get(
            '/api/cmdb/optimization/suggestions/',
            {'month': self.current_month},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload['month'], self.current_month)
        self.assertGreaterEqual(payload['suggestion_count'], 3)
        self.assertGreater(payload['total_potential_saving'], 0)
        self.assertEqual(payload['optimized_monthly_cost'], 1230.0)
        self.assertAlmostEqual(payload['saving_rate'], 41.4)
        self.assertTrue(any(item['label'] for item in payload['by_type']))
        titles = [item['title'] for item in payload['suggestions']]
        self.assertTrue(any('prod-db-01' in title for title in titles))
        self.assertTrue(any('test-host-01' in title for title in titles))
        self.assertTrue(any('idle-host-01' in title for title in titles))

    def test_cost_endpoints_fallback_when_month_is_invalid(self):
        cost_response = self.client.get('/api/cmdb/cost/report/', {'month': '2026-13'})
        optimization_response = self.client.get('/api/cmdb/optimization/suggestions/', {'month': 'not-a-month'})

        self.assertEqual(cost_response.status_code, 200)
        self.assertEqual(optimization_response.status_code, 200)
        self.assertEqual(cost_response.json()['month'], self.current_month)
        self.assertEqual(optimization_response.json()['month'], self.current_month)

    def test_current_month_cost_endpoints_do_not_persist_cost_records(self):
        cost_response = self.client.get('/api/cmdb/cost/report/', {'month': self.current_month})
        optimization_response = self.client.get(
            '/api/cmdb/optimization/suggestions/',
            {'month': self.current_month},
        )

        self.assertEqual(cost_response.status_code, 200)
        self.assertEqual(optimization_response.status_code, 200)
        self.assertEqual(
            CostRecord.objects.filter(month=self.current_month).count(),
            0,
        )


class CmdbTopologyTests(AuthenticatedTestCase):
    def setUp(self):
        super().setUp()
        app_type = CIType.objects.create(name='Application')
        host_type = CIType.objects.create(name='Host')

        self.core_prod = ConfigItem.objects.create(
            name='core-app-prod',
            ci_type=app_type,
            business_line='core',
            environment='prod',
            status='active',
            attributes={'ip_address': '10.0.0.10', 'monthly_cost': 500},
        )
        self.core_db = ConfigItem.objects.create(
            name='core-db-prod',
            ci_type=host_type,
            business_line='core',
            environment='prod',
            status='active',
            attributes={'ip_address': '10.0.0.11', 'monthly_cost': 800},
        )
        self.shared_cache = ConfigItem.objects.create(
            name='shared-cache-prod',
            ci_type=host_type,
            business_line='shared',
            environment='prod',
            status='active',
            attributes={'ip_address': '10.0.1.10', 'monthly_cost': 300},
        )
        CIRelation.objects.create(
            source=self.core_prod,
            target=self.core_db,
            relation_type='depends_on',
            description='Primary dependency',
        )
        CIRelation.objects.create(
            source=self.core_prod,
            target=self.shared_cache,
            relation_type='connects_to',
            description='Cross business dependency',
        )

    def test_topology_scope_neighbors_keeps_cross_scope_neighbors(self):
        response = self.client.get(
            '/api/cmdb/topology/data/',
            {
                'business_line': 'core',
                'environment': 'prod',
                'scope': 'neighbors',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        node_names = {node['name'] for node in payload['nodes']}
        self.assertEqual(payload['meta']['scope'], 'neighbors')
        self.assertIn('core-app-prod', node_names)
        self.assertIn('core-db-prod', node_names)
        self.assertIn('shared-cache-prod', node_names)
        self.assertEqual(len(payload['meta']['matched_node_ids']), 2)
        self.assertTrue(any(edge['target_name'] == 'shared-cache-prod' for edge in payload['edges']))
        self.assertTrue(any(edge['type'] == 'connects_to' for edge in payload['edges']))

    def test_topology_scope_exact_only_returns_matching_nodes(self):
        response = self.client.get(
            '/api/cmdb/topology/data/',
            {
                'business_line': 'core',
                'environment': 'prod',
                'scope': 'exact',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        node_names = {node['name'] for node in payload['nodes']}
        self.assertEqual(payload['meta']['scope'], 'exact')
        self.assertEqual(node_names, {'core-app-prod', 'core-db-prod'})
        self.assertFalse(any(edge['target_name'] == 'shared-cache-prod' for edge in payload['edges']))


class CmdbRelationValidationTests(AuthenticatedTestCase):
    def setUp(self):
        super().setUp()
        app_type = CIType.objects.create(name='Application')
        self.app_a = ConfigItem.objects.create(
            name='app-a',
            ci_type=app_type,
            business_line='core',
            environment='prod',
            status='active',
        )
        self.app_b = ConfigItem.objects.create(
            name='app-b',
            ci_type=app_type,
            business_line='core',
            environment='prod',
            status='active',
        )

    def test_relation_api_rejects_self_reference(self):
        response = self.client.post(
            '/api/cmdb/ci-relations/',
            {
                'source': self.app_a.id,
                'target': self.app_a.id,
                'relation_type': 'depends_on',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(CIRelation.objects.count(), 0)

    def test_relation_api_rejects_duplicate_relation(self):
        response = self.client.post(
            '/api/cmdb/ci-relations/',
            {
                'source': self.app_a.id,
                'target': self.app_b.id,
                'relation_type': 'depends_on',
            },
        )
        self.assertEqual(response.status_code, 201)

        duplicate_response = self.client.post(
            '/api/cmdb/ci-relations/',
            {
                'source': self.app_a.id,
                'target': self.app_b.id,
                'relation_type': 'depends_on',
            },
        )

        self.assertEqual(duplicate_response.status_code, 400)
        self.assertEqual(CIRelation.objects.count(), 1)


class CmdbResourceRequestTests(AuthenticatedTestCase):
    def setUp(self):
        super().setUp()
        core = ResourceNode.objects.create(name='core', node_type='biz')
        ResourceNode.objects.create(name='prod', node_type='env', parent=core)
        ResourceNode.objects.create(name='test', node_type='env', parent=core)

    def test_request_workflow_records_applicant_approver_and_completion(self):
        create_response = self.client.post(
            '/api/cmdb/resource-requests/',
            data=json.dumps({
                'title': 'Order service prod host expansion',
                'resource_type': 'host',
                'specification': '4C8G',
                'business_line': 'core',
                'environment': 'prod',
                'quantity': 1,
                'priority': 'high',
                'reason': 'Traffic increase requires one more node',
                'specs': {
                    'hostname': 'order-api-ecs-03',
                    'ip_address': '10.0.0.23',
                    'os_type': 'Alibaba Cloud Linux 3',
                    'admin_user': 'sre-core',
                    'instance_type': 'ecs.g7.xlarge',
                },
            }),
            content_type='application/json',
        )

        self.assertEqual(create_response.status_code, 201)
        request_id = create_response.json()['id']
        request_obj = ResourceRequest.objects.get(pk=request_id)
        self.assertEqual(request_obj.applicant, 'cmdb-admin')
        self.assertEqual(request_obj.status, 'pending')

        approve_response = self.client.post(
            f'/api/cmdb/resource-requests/{request_id}/approve/',
            {'comment': 'capacity approved'},
        )
        self.assertEqual(approve_response.status_code, 200)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.status, 'approved')
        self.assertEqual(request_obj.approver, 'cmdb-admin')
        self.assertEqual(request_obj.approval_comment, 'capacity approved')
        self.assertIsNotNone(request_obj.approved_at)

        complete_response = self.client.post(
            f'/api/cmdb/resource-requests/{request_id}/complete/',
            {'note': 'host provisioned and synced'},
        )
        self.assertEqual(complete_response.status_code, 200)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.status, 'completed')
        self.assertEqual(request_obj.fulfillment_note, 'host provisioned and synced')
        self.assertIsNotNone(request_obj.completed_at)

        host = Host.objects.get(hostname='order-api-ecs-03')
        self.assertEqual(host.ip_address, '10.0.0.23')
        self.assertEqual(host.business_line, 'core')
        self.assertEqual(host.environment, 'prod')
        self.assertEqual(host.admin_user, 'sre-core')
        self.assertEqual(host.status, 'online')

        ci = ConfigItem.objects.get(name='order-api-ecs-03')
        self.assertIn('ECS', ci.ci_type.name)
        self.assertEqual(ci.business_line, 'core')
        self.assertEqual(ci.environment, 'prod')
        self.assertEqual(ci.admin_user, 'sre-core')
        self.assertEqual(ci.status, 'active')
        self.assertEqual(ci.attributes['ip_address'], '10.0.0.23')
        self.assertEqual(ci.attributes['os_type'], 'Alibaba Cloud Linux 3')
        self.assertEqual(ci.attributes['instance_type'], 'ecs.g7.xlarge')
        self.assertEqual(ci.attributes['source'], 'host_request')
        self.assertEqual(ci.attributes['request_id'], request_id)

    def test_complete_requires_hostname_and_ip(self):
        request_obj = ResourceRequest.objects.create(
            title='Host request without delivery target',
            applicant='cmdb-admin',
            approver='cmdb-admin',
            resource_type='host',
            specification='2C4G',
            business_line='core',
            environment='prod',
            priority='medium',
            quantity=1,
            status='approved',
            reason='missing delivery info',
            specs={'os_type': 'Linux'},
            approved_at=timezone.now(),
        )

        response = self.client.post(
            f'/api/cmdb/resource-requests/{request_obj.id}/complete/',
            {'note': 'try to fulfill'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('detail', response.json())
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.status, 'approved')
        self.assertEqual(Host.objects.count(), 0)

    def test_submitter_only_sees_own_requests(self):
        ensure_builtin_rbac()
        submit_permission = PermissionDefinition.objects.get(code='cmdb.request.submit')
        role = Role.objects.create(code='request-submit-only', name='Request Submit Only')
        role.permissions.add(submit_permission)

        submitter = get_user_model().objects.create_user('submitter', 'submitter@example.com', 'Admin@123456')
        role.users.add(submitter)

        ResourceRequest.objects.create(
            title='鎴戠殑鐢宠',
            applicant='submitter',
            resource_type='涓绘満',
            business_line='core',
            environment='prod',
            reason='self',
        )
        ResourceRequest.objects.create(
            title='someone else request',
            applicant='someone-else',
            resource_type='Redis',
            business_line='core',
            environment='test',
            reason='other',
        )

        self.client.force_login(submitter)
        response = self.client.get('/api/cmdb/resource-requests/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        rows = payload['results'] if 'results' in payload else payload
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['applicant'], 'submitter')

    def test_request_api_only_accepts_host_resource_type(self):
        response = self.client.post(
            '/api/cmdb/resource-requests/',
            {
                'title': '鐢宠 Redis',
                'resource_type': 'Redis',
                'business_line': 'core',
                'environment': 'prod',
                'reason': 'not allowed',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('resource_type', response.json())


class CmdbSearchAndSyncTests(AuthenticatedTestCase):
    def test_ci_type_list_hides_alias_rows(self):
        CIType.objects.create(name='云主机(ECS)', color='#64748b')
        CIType.objects.create(name='云主机', color='#64748b')
        CIType.objects.create(name='K8s 集群', color='#0ea5e9')
        CIType.objects.create(name='K8s集群', color='#0ea5e9')

        response = self.client.get('/api/cmdb/ci-types/')
        self.assertEqual(response.status_code, 200)

        names = [item['name'] for item in response.json()]
        self.assertEqual(names.count('云主机(ECS)'), 1)
        self.assertEqual(names.count('K8s 集群'), 1)
        self.assertNotIn('云主机', names)
        self.assertNotIn('K8s集群', names)

    def test_config_item_api_search_supports_ip_and_ci_type_name(self):
        ci_type = CIType.objects.create(name='云主机(ECS)')
        ConfigItem.objects.create(
            name='order-api-ecs-01',
            ci_type=ci_type,
            business_line='core',
            environment='prod',
            admin_user='sre-core',
            status='active',
            attributes={
                'ip_address': '10.10.1.10',
                'description': '订单服务生产主机',
                'instance_type': 'ecs.g7.large',
            },
        )

        response = self.client.get('/api/cmdb/config-items/', {'search': '10.10.1.10'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

        response = self.client.get('/api/cmdb/config-items/', {'search': '云主机'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

    def test_config_item_api_fills_standard_ip_from_private_ip(self):
        ci_type = CIType.objects.create(name='云数据库')
        ConfigItem.objects.create(
            name='shared-rds-01',
            ci_type=ci_type,
            business_line='core',
            environment='prod',
            status='active',
            attributes={'private_ip': '10.20.2.20'},
        )

        response = self.client.get('/api/cmdb/config-items/', {'search': '10.20.2.20'})
        self.assertEqual(response.status_code, 200)
        row = response.json()['results'][0]
        self.assertEqual(row['attributes']['ip_address'], '10.20.2.20')

    def test_host_create_update_delete_syncs_to_cmdb(self):
        host = Host.objects.create(
            hostname='sync-host-01',
            ip_address='10.0.0.21',
            business_line='core',
            environment='prod',
            admin_user='ops-admin',
            os_type='Linux',
            description='由主机中心创建',
            status='online',
        )

        ci = ConfigItem.objects.get(name='sync-host-01')
        self.assertEqual(ci.attributes['ip_address'], '10.0.0.21')
        self.assertEqual(ci.business_line, 'core')
        self.assertEqual(ci.status, 'active')
        self.assertIn('ECS', ci.ci_type.name)

        host.ip_address = '10.0.0.22'
        host.description = '由主机中心更新'
        host.status = 'offline'
        host.save()

        ci.refresh_from_db()
        self.assertEqual(ci.attributes['ip_address'], '10.0.0.22')
        self.assertEqual(ci.attributes['description'], '由主机中心更新')
        self.assertEqual(ci.status, 'offline')

        host.delete()
        self.assertFalse(ConfigItem.objects.filter(name='sync-host-01').exists())

    def test_host_like_config_item_syncs_back_to_host(self):
        ci_type = CIType.objects.create(name='云主机(ECS)')
        ci = ConfigItem.objects.create(
            name='cmdb-host-01',
            ci_type=ci_type,
            business_line='retail',
            environment='test',
            admin_user='cmdb-owner',
            status='active',
            attributes={
                'ip_address': '10.0.1.15',
                'os_type': 'Alibaba Cloud Linux 3',
                'description': '由 CMDB 创建',
            },
        )

        host = Host.objects.get(hostname='cmdb-host-01')
        self.assertEqual(host.ip_address, '10.0.1.15')
        self.assertEqual(host.business_line, 'retail')
        self.assertEqual(host.environment, 'test')
        self.assertEqual(host.status, 'online')

        ci.status = 'offline'
        ci.attributes['description'] = '由 CMDB 更新'
        ci.save()

        host.refresh_from_db()
        self.assertEqual(host.status, 'offline')
        self.assertEqual(host.description, '由 CMDB 更新')

    def test_stats_merge_garbled_ci_type_names(self):
        good_type = CIType.objects.create(name='应用服务', color='#3b82f6')
        bad_type = CIType.objects.create(name='搴旂敤鏈嶅姟', color='#3b82f6')
        cloud_type = CIType.objects.create(name='云主机(ECS)', color='#64748b')
        cloud_alias_type = CIType.objects.create(name='云主机', color='#64748b')
        k8s_type = CIType.objects.create(name='K8s 集群', color='#0ea5e9')
        k8s_alias_type = CIType.objects.create(name='K8s集群', color='#0ea5e9')
        ConfigItem.objects.create(name='app-a', ci_type=good_type, status='active')
        ConfigItem.objects.create(name='app-b', ci_type=bad_type, status='active')
        ConfigItem.objects.create(name='host-a', ci_type=cloud_type, status='active')
        ConfigItem.objects.create(name='host-b', ci_type=cloud_alias_type, status='active')
        ConfigItem.objects.create(name='cluster-a', ci_type=k8s_type, status='active')
        ConfigItem.objects.create(name='cluster-b', ci_type=k8s_alias_type, status='active')

        response = self.client.get('/api/cmdb/config-items/stats/')
        self.assertEqual(response.status_code, 200)

        by_type = response.json()['by_type']
        app_entry = next(item for item in by_type if item['ci_type__name'] == '应用服务')
        host_entry = next(item for item in by_type if item['ci_type__name'] == '云主机(ECS)')
        k8s_entry = next(item for item in by_type if item['ci_type__name'] == 'K8s 集群')
        self.assertEqual(app_entry['count'], 2)
        self.assertEqual(host_entry['count'], 2)
        self.assertEqual(k8s_entry['count'], 2)


