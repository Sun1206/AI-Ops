from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from cmdb.models import CIRelation, ConfigItem, ResourceNode
from ops import deployer
from ops.models import (
    Deployment,
    DeploymentApprovalFlow,
    DeploymentApprovalNode,
    DeploymentApprovalStep,
    DockerHost,
    Host,
    K8sCluster,
)
class AppReleaseApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_superuser('ops-admin', 'ops@example.com', 'Admin@123456')
        self.client.force_authenticate(user=self.user)
        self.biz_node = ResourceNode.objects.create(name='电商线', node_type='biz')
        ResourceNode.objects.create(name='prod', node_type='env', parent=self.biz_node)
        ResourceNode.objects.create(name='test', node_type='env', parent=self.biz_node)
        ResourceNode.objects.create(name='dev', node_type='env', parent=self.biz_node)
        self.host = Host.objects.create(hostname='app-host-01', ip_address='10.0.0.11')
        self.docker_host = DockerHost.objects.create(name='docker-test-env', ip_address='10.0.0.11', status='connected')
        self.cluster = K8sCluster.objects.create(name='demo-cluster', kubeconfig='demo')

    def test_create_docker_release_starts_as_pending_approval(self):
        response = self.client.post(
            '/api/deployments/',
            {
                'app_name': 'order-service',
                'business_line': '电商线',
                'version': '2.3.1',
                'image': 'registry.internal/order-service:2.3.1',
                'environment': 'test',
                'deploy_mode': 'docker_compose',
                'docker_host': self.docker_host.id,
                'change_summary': '订单服务预发布',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        deployment = Deployment.objects.get()
        self.assertEqual(deployment.approval_status, 'pending')
        self.assertEqual(deployment.status, 'pending')
        self.assertEqual(deployment.submitter, self.user.username)
        self.assertEqual(deployment.docker_host_id, self.docker_host.id)

    @patch('ops.views.deployer.start_deployment_thread')
    def test_approve_release_starts_execution_thread(self, mock_start_thread):
        deployment = Deployment.objects.create(
            app_name='gateway',
            business_line='电商线',
            version='1.0.0',
            image='registry.internal/gateway:1.0.0',
            environment='prod',
            deploy_mode='docker_compose',
            docker_host=self.docker_host,
            submitter='dev-a',
        )

        response = self.client.post(
            f'/api/deployments/{deployment.id}/approve/',
            {'comment': '审批通过'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        deployment.refresh_from_db()
        self.assertEqual(deployment.approval_status, 'approved')
        self.assertEqual(deployment.approver, self.user.username)
        mock_start_thread.assert_called_once_with(deployment.id)

    def test_rollback_creates_new_pending_release(self):
        previous = Deployment.objects.create(
            app_name='billing-service',
            business_line='电商线',
            version='1.9.0',
            image='registry.internal/billing-service:1.9.0',
            environment='prod',
            deploy_mode='docker_compose',
            docker_host=self.docker_host,
            approval_status='approved',
            approver='ops-a',
            status='running',
            execution_count=1,
            is_current=False,
        )
        current = Deployment.objects.create(
            app_name='billing-service',
            business_line='电商线',
            version='2.0.0',
            image='registry.internal/billing-service:2.0.0',
            environment='prod',
            deploy_mode='docker_compose',
            docker_host=self.docker_host,
            approval_status='approved',
            approver='ops-a',
            status='running',
            execution_count=1,
            is_current=True,
            previous_success=previous,
        )

        response = self.client.post(
            f'/api/deployments/{current.id}/rollback/',
            {'change_summary': '线上异常回滚'},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        rollback_release = Deployment.objects.exclude(pk__in=[previous.id, current.id]).get()
        self.assertEqual(rollback_release.action_type, 'rollback')
        self.assertEqual(rollback_release.version, '1.9.0')
        self.assertEqual(rollback_release.rollback_source_id, current.id)
        self.assertEqual(rollback_release.approval_status, 'pending')

    def test_create_batch_release_keeps_strategy_fields(self):
        response = self.client.post(
            '/api/deployments/',
            {
                'app_name': 'user-center',
                'business_line': '电商线',
                'version': '3.1.0',
                'environment': 'test',
                'deploy_mode': 'docker_compose',
                'docker_host': self.docker_host.id,
                'release_strategy': 'batch',
                'batch_total': 3,
                'batch_size': 2,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        deployment = Deployment.objects.get(app_name='user-center')
        self.assertEqual(deployment.release_strategy, 'batch')
        self.assertEqual(deployment.batch_total, 3)
        self.assertEqual(deployment.batch_size, 2)


class AppReleaseApprovalFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_superuser('ops-admin', 'ops@example.com', 'Admin@123456')
        self.client.force_authenticate(user=self.user)
        self.biz_node = ResourceNode.objects.create(name='电商线', node_type='biz')
        ResourceNode.objects.create(name='prod', node_type='env', parent=self.biz_node)
        ResourceNode.objects.create(name='test', node_type='env', parent=self.biz_node)
        ResourceNode.objects.create(name='dev', node_type='env', parent=self.biz_node)
        self.host = Host.objects.create(hostname='approval-host', ip_address='10.0.0.12')
        self.docker_host = DockerHost.objects.create(name='docker-approval-env', ip_address='10.0.0.12', status='connected')

    def test_create_approval_flow_via_api(self):
        response = self.client.post(
            '/api/deployment-approval-flows/',
            {
                'name': '生产双节点审批',
                'environment': 'prod',
                'is_active': True,
                'description': '生产环境企业发布审批',
                'nodes': [
                    {'name': '研发负责人', 'order': 1, 'approver_type': 'user', 'approver_value': 'ops-admin'},
                    {'name': '运维复核', 'order': 2, 'approver_type': 'user', 'approver_value': 'ops-admin'},
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        flow = DeploymentApprovalFlow.objects.get()
        self.assertEqual(flow.nodes.count(), 2)
        self.assertEqual(flow.created_by, self.user.username)

    @patch('ops.views.deployer.start_deployment_thread')
    def test_multi_node_approval_progression(self, mock_start_thread):
        flow = DeploymentApprovalFlow.objects.create(
            name='预发布审批流',
            environment='test',
            created_by=self.user.username,
            is_active=True,
        )
        DeploymentApprovalNode.objects.create(flow=flow, name='研发审核', order=1, approver_type='user', approver_value='ops-admin')
        DeploymentApprovalNode.objects.create(flow=flow, name='运维审核', order=2, approver_type='user', approver_value='ops-admin')

        create_res = self.client.post(
            '/api/deployments/',
            {
                'app_name': 'gateway',
                'business_line': '电商线',
                'version': '1.0.1',
                'environment': 'test',
                'deploy_mode': 'docker_compose',
                'docker_host': self.docker_host.id,
            },
            format='json',
        )
        self.assertEqual(create_res.status_code, 201)
        deployment = Deployment.objects.get(app_name='gateway')
        self.assertEqual(deployment.approval_steps.count(), 2)
        self.assertEqual(deployment.current_approval_step.node_name, '研发审核')

        first_res = self.client.post(f'/api/deployments/{deployment.id}/approve/', {'comment': '第一节点通过'}, format='json')
        self.assertEqual(first_res.status_code, 200)
        deployment.refresh_from_db()
        self.assertEqual(deployment.approval_status, 'pending')
        self.assertEqual(deployment.current_approval_step.node_name, '运维审核')
        mock_start_thread.assert_not_called()

        second_res = self.client.post(f'/api/deployments/{deployment.id}/approve/', {'comment': '最终通过'}, format='json')
        self.assertEqual(second_res.status_code, 200)
        deployment.refresh_from_db()
        self.assertEqual(deployment.approval_status, 'approved')
        mock_start_thread.assert_called_once_with(deployment.id)

    def test_reject_on_intermediate_step_marks_release_rejected(self):
        flow = DeploymentApprovalFlow.objects.create(
            name='生产审批流',
            environment='prod',
            created_by=self.user.username,
            is_active=True,
        )
        DeploymentApprovalNode.objects.create(flow=flow, name='运维审核', order=1, approver_type='user', approver_value='ops-admin')

        deployment = Deployment.objects.create(
            app_name='erp',
            business_line='电商线',
            version='5.0.0',
            image='registry.internal/erp:5.0.0',
            environment='prod',
            deploy_mode='docker_compose',
            docker_host=self.docker_host,
            submitter='dev-a',
            approval_flow=flow,
        )
        DeploymentApprovalStep.objects.create(
            deployment=deployment,
            flow=flow,
            node_name='运维审核',
            node_order=1,
            approver_type='user',
            approver_value='ops-admin',
            is_current=True,
        )

        response = self.client.post(f'/api/deployments/{deployment.id}/reject/', {'comment': '风险未消除'}, format='json')

        self.assertEqual(response.status_code, 200)
        deployment.refresh_from_db()
        self.assertEqual(deployment.approval_status, 'rejected')
        self.assertEqual(deployment.status, 'rejected')
        self.assertEqual(deployment.approval_steps.first().status, 'rejected')


class AppReleaseRuntimeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.biz_node = ResourceNode.objects.create(name='电商线', node_type='biz')
        ResourceNode.objects.create(name='prod', node_type='env', parent=self.biz_node)
        ResourceNode.objects.create(name='test', node_type='env', parent=self.biz_node)
        ResourceNode.objects.create(name='dev', node_type='env', parent=self.biz_node)
        self.host = Host.objects.create(hostname='runtime-host', ip_address='10.0.0.21')
        self.docker_host = DockerHost.objects.create(name='docker-runtime-env', ip_address='10.0.0.21', status='connected')

    @patch('ops.deployer._get_ssh_client')
    @patch('ops.deployer._ssh_exec')
    def test_get_docker_runtime_status_parses_json_lines(self, mock_ssh_exec, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        mock_ssh_exec.return_value = (
            0,
            '{"Name":"order-service","State":"running","Publishers":"0.0.0.0:8080->8080/tcp"}\n',
            '',
        )

        deployment = Deployment.objects.create(
            app_name='order-service',
            business_line='电商线',
            version='2.3.1',
            image='registry.internal/order-service:2.3.1',
            environment='test',
            deploy_mode='docker_compose',
            docker_host=self.docker_host,
            approval_status='approved',
            status='running',
            is_current=True,
            deploy_dir='/opt/sxdevops/apps/order-service-test',
        )

        payload = deployer.get_service_status(deployment)
        self.assertEqual(payload['mode'], 'docker_compose')
        self.assertEqual(payload['items'][0]['name'], 'order-service')

    @patch('ops.deployer._get_ssh_client')
    def test_get_docker_runtime_status_uses_demo_fallback(self, mock_get_client):
        deployment = Deployment.objects.create(
            app_name='order-center',
            business_line='电商线',
            version='2.6.0',
            image='registry.demo.local/order-center:v2.6.0',
            environment='test',
            deploy_mode='docker_compose',
            docker_host=self.docker_host,
            approval_status='approved',
            status='running',
            is_current=True,
            deploy_dir='/opt/sxdevops/apps/order-center-test',
            release_strategy='batch',
            batch_total=3,
            batch_current=2,
            container_port=8081,
            service_port=8081,
        )

        payload = deployer.get_service_status(deployment)
        self.assertEqual(payload['mode'], 'docker_compose')
        self.assertIn('Demo Docker 环境', payload['summary'])
        self.assertEqual(payload['items'][0]['name'], deployment.release_name_display)
        mock_get_client.assert_not_called()

    @patch('ops.deployer._k8s_runtime_status')
    def test_get_service_status_returns_stale_cache_when_k8s_runtime_times_out(self, mock_k8s_runtime_status):
        cluster = K8sCluster.objects.create(
            name='runtime-k8s',
            kubeconfig='apiVersion: v1\nkind: Config\nclusters: []\ncontexts: []\n',
        )
        deployment = Deployment.objects.create(
            app_name='checkout',
            business_line='retail',
            version='2.8.0',
            image='registry.internal/checkout:2.8.0',
            environment='prod',
            deploy_mode='k8s',
            cluster=cluster,
            namespace='production',
            approval_status='approved',
            status='running',
            is_current=True,
        )
        mock_k8s_runtime_status.return_value = {
            'mode': 'k8s',
            'summary': '工作负载数量: 2',
            'items': [{'kind': 'Deployment', 'name': 'checkout', 'state': 'Available', 'ready': '2/2'}],
        }

        first_payload = deployer.get_service_status(deployment)

        self.assertEqual(first_payload['summary'], '工作负载数量: 2')

        mock_k8s_runtime_status.side_effect = TimeoutError('connect timed out')
        cache.delete(deployer._service_status_cache_key(deployment))
        second_payload = deployer.get_service_status(deployment)

        self.assertTrue(second_payload['degraded'])
        self.assertEqual(second_payload['summary'], '工作负载数量: 2')
        self.assertIn('缓存结果', second_payload['message'])

    def test_advance_batch_updates_progress(self):
        deployment = Deployment.objects.create(
            app_name='crm',
            business_line='电商线',
            version='1.2.0',
            image='registry.internal/crm:1.2.0',
            environment='prod',
            deploy_mode='docker_compose',
            docker_host=self.docker_host,
            approval_status='approved',
            status='running',
            is_current=True,
            release_strategy='batch',
            batch_total=3,
            batch_current=1,
            batch_size=2,
        )

        deployer.advance_batch(deployment, actor='ops-admin', change_summary='推进第二批')
        deployment.refresh_from_db()
        self.assertEqual(deployment.batch_current, 2)
        self.assertIn('第 2/3 批', deployment.deploy_log)

    def test_sync_deployment_to_cmdb_creates_config_item(self):
        deployment = Deployment.objects.create(
            app_name='member-center',
            business_line='电商线',
            version='2.1.0',
            image='registry.internal/member-center:2.1.0',
            environment='prod',
            deploy_mode='docker_compose',
            docker_host=self.docker_host,
            approval_status='approved',
            status='running',
            is_current=True,
            submitter='dev-a',
            deployer='ops-admin',
        )

        deployer.sync_deployment_to_cmdb(deployment)

        ci = ConfigItem.objects.get(name='member-center-prod')
        self.assertEqual(ci.business_line, '电商线')
        self.assertEqual(ci.environment, 'prod')
        self.assertEqual(ci.status, 'active')
        self.assertEqual(ci.attributes['deployment_id'], deployment.id)
        relation = CIRelation.objects.get(source=ci, relation_type='runs_on')
        self.assertEqual(relation.target.name, self.docker_host.name)
