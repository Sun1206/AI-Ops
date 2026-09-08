from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from kubernetes.client.exceptions import ApiException

from marketplace import deployer
from marketplace.models import ServiceDeployment, ServiceTemplate
from ops.models import Host, K8sCluster
from ops.management.commands.seed_data import create_marketplace_deployment, seed_marketplace_demo


class MarketplaceDeployApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_superuser(
            'market-admin',
            'market@example.com',
            'Admin@123456',
        )
        self.client.force_authenticate(user=self.user)
        self.host = Host.objects.create(hostname='node-01', ip_address='10.0.0.11')
        self.cluster = K8sCluster.objects.create(name='demo-cluster', kubeconfig='demo')
        self.template = ServiceTemplate.objects.create(
            name='Redis',
            icon='redis',
            category='cache',
            description='缓存服务',
            versions=['7.0'],
            docker_compose_template='services:\n  redis:\n    image: redis:{{version}}\n',
            k8s_manifest_template=(
                'apiVersion: apps/v1\n'
                'kind: Deployment\n'
                'metadata:\n'
                '  name: {{release_name}}\n'
                'spec:\n'
                '  replicas: {{replicas}}\n'
                '  selector:\n'
                '    matchLabels:\n'
                '      app: {{release_name}}\n'
                '  template:\n'
                '    metadata:\n'
                '      labels:\n'
                '        app: {{release_name}}\n'
                '    spec:\n'
                '      containers:\n'
                '        - name: redis\n'
                '          image: redis:{{version}}\n'
                '---\n'
                'apiVersion: v1\n'
                'kind: Service\n'
                'metadata:\n'
                '  name: {{release_name}}\n'
                'spec:\n'
                '  selector:\n'
                '    app: {{release_name}}\n'
                '  ports:\n'
                '    - port: 6379\n'
                '      targetPort: 6379\n'
            ),
        )

    @patch('marketplace.views.threading.Thread')
    def test_deploy_service_defaults_to_docker_compose(self, mock_thread):
        mock_thread.return_value = MagicMock()

        response = self.client.post(
            '/api/marketplace/deploy/',
            {
                'template_id': self.template.id,
                'host_id': self.host.id,
                'version': '7.0',
                'env_config': {'password': 'secret'},
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        deployment = ServiceDeployment.objects.get()
        self.assertEqual(deployment.deploy_mode, 'docker_compose')
        self.assertEqual(deployment.host_id, self.host.id)
        self.assertIsNone(deployment.cluster_id)
        mock_thread.assert_called_once()

    def test_template_list_includes_both_deploy_modes(self):
        response = self.client.get('/api/marketplace/templates/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        redis = next(item for item in payload if item['name'] == 'Redis')
        self.assertEqual(redis['available_deploy_modes'], ['docker_compose', 'k8s'])

    @patch('marketplace.views.threading.Thread')
    def test_deploy_service_can_target_k8s_cluster(self, mock_thread):
        mock_thread.return_value = MagicMock()

        response = self.client.post(
            '/api/marketplace/deploy/',
            {
                'template_id': self.template.id,
                'deploy_mode': 'k8s',
                'cluster_id': self.cluster.id,
                'namespace': 'middleware',
                'release_name': 'redis-cache',
                'replicas': 2,
                'version': '7.0',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        deployment = ServiceDeployment.objects.get()
        self.assertEqual(deployment.deploy_mode, 'k8s')
        self.assertEqual(deployment.cluster_id, self.cluster.id)
        self.assertEqual(deployment.namespace, 'middleware')
        self.assertEqual(deployment.release_name, 'redis-cache')
        self.assertEqual(deployment.replicas, 2)
        self.assertIsNone(deployment.host_id)
        mock_thread.assert_called_once()


class MarketplaceK8sDeployerTests(TestCase):
    def setUp(self):
        self.cluster = K8sCluster.objects.create(name='prod-cluster', kubeconfig='apiVersion: v1')
        self.template = ServiceTemplate.objects.create(
            name='MySQL',
            icon='mysql',
            category='database',
            description='数据库',
            versions=['8.0'],
            k8s_manifest_template=(
                'apiVersion: apps/v1\n'
                'kind: Deployment\n'
                'metadata:\n'
                '  name: {{release_name}}\n'
                'spec:\n'
                '  replicas: {{replicas}}\n'
                '  selector:\n'
                '    matchLabels:\n'
                '      app: {{release_name}}\n'
                '  template:\n'
                '    metadata:\n'
                '      labels:\n'
                '        app: {{release_name}}\n'
                '    spec:\n'
                '      containers:\n'
                '        - name: mysql\n'
                '          image: mysql:{{version}}\n'
                '          ports:\n'
                '            - containerPort: 3306\n'
                '---\n'
                'apiVersion: v1\n'
                'kind: Service\n'
                'metadata:\n'
                '  name: {{release_name}}\n'
                'spec:\n'
                '  ports:\n'
                '    - port: 3306\n'
                '      targetPort: 3306\n'
            ),
        )

    @patch('marketplace.deployer.k8s_utils.create_from_dict')
    @patch('marketplace.deployer._get_k8s_client')
    @patch('marketplace.deployer._is_demo', return_value=False)
    def test_deploy_service_applies_k8s_manifest(self, _mock_is_demo, mock_get_k8s_client, mock_create_from_dict):
        client_module = MagicMock()
        client_module.CoreV1Api.return_value.read_namespace.side_effect = ApiException(status=404)
        mock_get_k8s_client.return_value = client_module

        deployment = ServiceDeployment.objects.create(
            template=self.template,
            deploy_mode='k8s',
            cluster=self.cluster,
            namespace='database',
            release_name='mysql-db',
            replicas=2,
            version='8.0',
        )

        deployer.deploy_service(deployment.id)
        deployment.refresh_from_db()

        self.assertEqual(deployment.status, 'running')
        self.assertEqual(deployment.deploy_dir, 'k8s://prod-cluster/database/mysql-db')
        client_module.CoreV1Api.return_value.create_namespace.assert_called_once()
        self.assertEqual(mock_create_from_dict.call_count, 2)

    @patch('marketplace.deployer._get_k8s_client')
    @patch('marketplace.deployer._is_demo', return_value=False)
    def test_stop_service_scales_k8s_workload_to_zero(self, _mock_is_demo, mock_get_k8s_client):
        apps_api = MagicMock()
        apps_api.list_namespaced_deployment.return_value.items = [MagicMock(metadata=MagicMock(name='mysql-db'))]
        mock_get_k8s_client.return_value.AppsV1Api.return_value = apps_api

        deployment = ServiceDeployment.objects.create(
            template=self.template,
            deploy_mode='k8s',
            cluster=self.cluster,
            namespace='database',
            release_name='mysql-db',
            replicas=2,
            version='8.0',
            status='running',
        )

        deployer.stop_service(deployment)
        deployment.refresh_from_db()

        self.assertEqual(deployment.status, 'stopped')
        apps_api.patch_namespaced_deployment_scale.assert_called_once()


class MarketplaceSeedTemplatesTests(TestCase):
    def test_seed_templates_adds_new_builtin_templates(self):
        call_command('seed_templates')

        names = set(ServiceTemplate.objects.values_list('name', flat=True))
        self.assertTrue({'MongoDB', 'Java', 'Python', 'Go', 'Node.js'}.issubset(names))

        mongodb = ServiceTemplate.objects.get(name='MongoDB')
        self.assertIn('docker_compose', mongodb.available_deploy_modes)
        self.assertIn('k8s', mongodb.available_deploy_modes)

        java = ServiceTemplate.objects.get(name='Java')
        self.assertEqual(java.versions[0], '3.9.9-eclipse-temurin-21')
        self.assertIn('maven_mirror_url', [item['key'] for item in java.env_schema])

    def test_seed_marketplace_demo_creates_demo_deployments(self):
        call_command('seed_templates')
        hosts = [
            Host.objects.create(hostname='redis-01', ip_address='192.168.1.40'),
            Host.objects.create(hostname='db-master', ip_address='192.168.1.30'),
            Host.objects.create(hostname='nginx-lb-01', ip_address='192.168.1.50'),
        ]

        class Stdout:
            def write(self, _message):
                return None

        seed_marketplace_demo(Stdout(), hosts)

        self.assertGreaterEqual(ServiceDeployment.objects.count(), 7)
        self.assertTrue(ServiceDeployment.objects.filter(deploy_mode='docker_compose').exists())
        self.assertTrue(ServiceDeployment.objects.filter(deploy_mode='k8s').exists())

    @patch('ops.management.commands.seed_data.connection.introspection.get_table_description')
    def test_create_marketplace_deployment_uses_backend_introspection(self, mock_table_description):
        template = ServiceTemplate.objects.create(
            name='Redis',
            icon='redis',
            category='cache',
            description='cache',
            versions=['7.0'],
            docker_compose_template='services:\n  redis:\n    image: redis:{{version}}\n',
        )
        host = Host.objects.create(hostname='redis-01', ip_address='192.168.1.40')
        db_columns = [
            field.column
            for field in ServiceDeployment._meta.concrete_fields
            if field.column != ServiceDeployment._meta.pk.column
        ]
        mock_table_description.return_value = [SimpleNamespace(name=name) for name in db_columns]

        create_marketplace_deployment({
            'template': template,
            'deploy_mode': 'docker_compose',
            'host': host,
            'version': '7.0',
            'status': 'running',
            'env_config': {'port': '6379'},
            'deployer': 'ops-demo',
            'deploy_dir': '/opt/sxdevops/redis',
            'deploy_log': '[INFO] Docker Compose deploy succeeded',
        })

        mock_table_description.assert_called_once()
        self.assertEqual(ServiceDeployment.objects.get().host_id, host.id)
