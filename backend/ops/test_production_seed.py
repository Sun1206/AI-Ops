from django.contrib.auth import get_user_model
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from aiops.models import AIOpsChatMessage, AIOpsChatSession
from eventwall.models import EventRecord
from ops.management.production_seed.aiops_data import seed_aiops
from ops.management.production_seed.alerting import seed_alerting
from ops.management.production_seed.audit_data import seed_audit_data
from ops.management.production_seed.common import SeedStats, resolve_base_objects
from ops.management.production_seed.log_data import seed_log_data
from ops.management.production_seed.observability import seed_observability
from ops.management.production_seed.runtime_data import seed_runtime_data
from ops.management.production_seed.task_resources import seed_task_resources
from ops.models import Alert, Deployment, Host, LogEntry


class ProductionSeedRuntimeTests(TestCase):
    def test_runtime_seed_creates_medium_scale_dashboard_records(self):
        stats = SeedStats()
        base = resolve_base_objects(stats)

        context = seed_runtime_data(stats, base)

        self.assertEqual(len(context['hosts']), 72)
        self.assertEqual(len(context['deployments']), 180)
        self.assertGreaterEqual(Host.objects.count(), 72)
        self.assertGreaterEqual(Deployment.objects.count(), 180)
        self.assertEqual(
            Deployment.objects.filter(deploy_dir__startswith='/srv/releases/').count(),
            180,
        )


class ProductionSeedAlertTests(TestCase):
    def test_alert_seed_creates_diverse_recent_events(self):
        stats = SeedStats()
        base = resolve_base_objects(stats)

        context = seed_alerting(stats, base)
        generated = Alert.objects.filter(
            raw_payload__seed_namespace='production-alerts',
        )

        self.assertEqual(generated.count(), 260)
        self.assertGreaterEqual(
            generated.values('last_received_at').distinct().count(),
            100,
        )
        self.assertEqual(
            set(generated.values_list('source_type', flat=True)),
            {'prometheus', 'nightingale', 'zabbix', 'aliyun'},
        )
        self.assertEqual(len(context['alerts']), 260)


class ProductionSeedLogTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = get_user_model().objects.create_superuser(
            'log-admin',
            'log-admin@corp.internal',
            'Admin@123456',
        )
        self.client.force_authenticate(self.admin)

    def test_log_seed_creates_600_recent_production_logs(self):
        stats = SeedStats()
        base = resolve_base_objects(stats)
        runtime = seed_runtime_data(stats, base)

        logs = seed_log_data(stats, runtime)

        self.assertEqual(len(logs), 600)
        self.assertEqual(
            LogEntry.objects.filter(message__contains='request_id=OPS-').count(),
            600,
        )
        self.assertFalse(
            LogEntry.objects.filter(message__iregex=r'demo|mock').exists(),
        )
        self.assertGreaterEqual(
            LogEntry.objects.values('service').distinct().count(),
            6,
        )

        response = self.client.post(
            '/api/log/query/',
            {
                'provider': 'loki',
                'query': '{service=~".+"}',
                'limit': 100,
                'start_ms': int((timezone.now() - timedelta(days=31)).timestamp() * 1000),
                'config': {'demo_mode': True},
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertGreaterEqual(response.json()['total'], 600)
        self.assertNotIn('演示', response.json()['source'])


class ProductionSeedAIOpsTests(TestCase):
    def test_aiops_seed_creates_multi_turn_session_history(self):
        stats = SeedStats()
        base = resolve_base_objects(stats)
        task_context = seed_task_resources(stats, base)
        alert_context = seed_alerting(stats, base)
        obs_context = seed_observability(stats, base)

        seed_aiops(stats, base, task_context, alert_context, obs_context)

        sessions = AIOpsChatSession.objects.filter(
            context__seed_namespace='production-sessions',
        )
        messages = AIOpsChatMessage.objects.filter(session__in=sessions)
        self.assertEqual(sessions.count(), 16)
        self.assertEqual(messages.count(), 96)
        self.assertTrue(all(
            session.messages.count() == 6
            for session in sessions
        ))


class ProductionSeedAuditTests(TestCase):
    def test_audit_seed_creates_records_and_normalizes_legacy_sources(self):
        EventRecord.objects.create(
            module='ops',
            category='seed',
            action='create',
            title='历史初始化记录',
            source_type=EventRecord.SOURCE_SEED,
            is_demo=True,
        )
        stats = SeedStats()
        base = resolve_base_objects(stats)

        events = seed_audit_data(stats, base)

        self.assertEqual(len(events), 300)
        self.assertEqual(
            EventRecord.objects.filter(
                correlation_id__startswith='prod-audit-',
            ).count(),
            300,
        )
        self.assertFalse(EventRecord.objects.filter(is_demo=True).exists())
        self.assertFalse(EventRecord.objects.filter(
            source_type=EventRecord.SOURCE_SEED,
        ).exists())


class ProductionSeedCommandTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        admin = get_user_model().objects.create_superuser(
            'seed-admin',
            'seed-admin@corp.internal',
            'Admin@123456',
        )
        self.client.force_authenticate(admin)

    def _generated_counts(self):
        return {
            'hosts': Host.objects.filter(hostname__startswith='prod-').count(),
            'deployments': Deployment.objects.filter(
                deploy_dir__startswith='/srv/releases/',
            ).count(),
            'alerts': Alert.objects.filter(
                raw_payload__seed_namespace='production-alerts',
            ).count(),
            'logs': LogEntry.objects.filter(
                message__contains='request_id=OPS-',
            ).count(),
            'sessions': AIOpsChatSession.objects.filter(
                context__seed_namespace='production-sessions',
            ).count(),
            'audit': EventRecord.objects.filter(
                correlation_id__startswith='prod-audit-',
            ).count(),
        }

    def test_command_is_idempotent_and_key_pages_have_data(self):
        call_command('seed_production_data')
        first_counts = self._generated_counts()
        call_command('seed_production_data')

        self.assertEqual(first_counts, self._generated_counts())
        self.assertEqual(first_counts, {
            'hosts': 72,
            'deployments': 180,
            'alerts': 260,
            'logs': 600,
            'sessions': 16,
            'audit': 300,
        })

        for path in (
            '/api/observability/overview/',
            '/api/alerts/',
            '/api/events/operation_audit/',
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, (path, response.content))
