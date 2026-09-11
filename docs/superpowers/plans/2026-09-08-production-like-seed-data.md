# Production-like Seed Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe, repeatable production-like records so every currently accessible empty task-resource, alerting, observability, and AIOps page displays coherent data.

**Architecture:** Implement one orchestration management command backed by four focused seed modules and a shared idempotency/time helper. The command writes only ORM records inside one transaction, reuses existing objects when possible, and stores stable seed keys in JSON fields for history tables without natural unique keys. Docker startup invokes the additive command after the existing base seed so the populated state survives container recreation.

**Tech Stack:** Python 3.12, Django ORM/management commands, Django TestCase, MySQL 8 JSON lookups, Docker Compose, PowerShell HTTP verification.

---

## Scope and file map

The four domains share one transaction, existing Host/Alert/User/DataSource objects, and cross-domain IDs used by AIOps knowledge environments, so they remain one implementation plan rather than four independent projects.

**Create:**

- `backend/ops/management/production_seed/__init__.py` — package exports.
- `backend/ops/management/production_seed/common.py` — stable upsert, backdating, counters, and base-object resolution.
- `backend/ops/management/production_seed/task_resources.py` — task resource groups and resources.
- `backend/ops/management/production_seed/alerting.py` — recipients, groups, channels, rules, mute records, notification history, and action history.
- `backend/ops/management/production_seed/observability.py` — metric/tracing sources, source links, and Grafana configuration.
- `backend/ops/management/production_seed/aiops_data.py` — knowledge environments, sessions, messages, invocations, actions, external tasks, Runbooks, and review knowledge.
- `backend/ops/management/commands/seed_production_data.py` — transactional command and summary output.
- `backend/ops/test_seed_production_data.py` — command, idempotency, safety, and cross-domain tests.

**Modify:**

- `docker/entrypoint.sh` — invoke the additive seed after `seed_data`.
- `docker-compose.yml` — enable the additive seed with `SXDEVOPS_SEED_PRODUCTION_DATA: "1"`.

No migration or frontend change is expected. The target directory is not a Git repository, so commit steps are replaced with explicit verification checkpoints and a pre-edit backup.

### Task 1: Establish the command contract and rollback checkpoint

**Files:**

- Create: `backend/ops/test_seed_production_data.py`
- Backup before edits: the nine files listed in the file map, when present

- [ ] **Step 1: Create a recoverable source backup**

Run from the project root:

```powershell
$backup = 'C:\Users\sunyupeng\Documents\Codex\2026-09-08\c-users-sunyupeng-pycharmprojects-ai-ops\work\production-seed-source-backup.zip'
$paths = @(
  'backend\ops\management\production_seed',
  'backend\ops\management\commands\seed_production_data.py',
  'backend\ops\test_seed_production_data.py',
  'docker\entrypoint.sh',
  'docker-compose.yml'
)
$existing = $paths | Where-Object { Test-Path -LiteralPath $_ }
if ($existing) { Compress-Archive -LiteralPath $existing -DestinationPath $backup -Force }
```

Expected: the command exits successfully; if any target files already exist, the zip contains their original versions.

- [ ] **Step 2: Write the first failing command test**

Create `backend/ops/test_seed_production_data.py` with:

```python
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from aiops.models import AIOpsKnowledgeEnvironment
from ops.models import AlertRecipient, MetricDataSource, TaskResourceGroup


class SeedProductionDataCommandTests(TestCase):
    def test_command_populates_each_target_domain(self):
        output = StringIO()

        call_command('seed_production_data', stdout=output)

        self.assertGreaterEqual(TaskResourceGroup.objects.count(), 5)
        self.assertGreaterEqual(AlertRecipient.objects.count(), 8)
        self.assertGreaterEqual(MetricDataSource.objects.count(), 2)
        self.assertGreaterEqual(AIOpsKnowledgeEnvironment.objects.count(), 3)
        self.assertIn('production seed complete', output.getvalue().lower())
```

- [ ] **Step 3: Run the test to verify the command is missing**

Run:

```powershell
docker compose exec -T sxdevops python manage.py test ops.test_seed_production_data.SeedProductionDataCommandTests.test_command_populates_each_target_domain -v 2
```

Expected: FAIL with `Unknown command: 'seed_production_data'`.

### Task 2: Add shared idempotency helpers and the transactional command

**Files:**

- Create: `backend/ops/management/production_seed/__init__.py`
- Create: `backend/ops/management/production_seed/common.py`
- Create: `backend/ops/management/production_seed/task_resources.py`
- Create: `backend/ops/management/production_seed/alerting.py`
- Create: `backend/ops/management/production_seed/observability.py`
- Create: `backend/ops/management/production_seed/aiops_data.py`
- Create: `backend/ops/management/commands/seed_production_data.py`
- Modify: `backend/ops/test_seed_production_data.py`

- [ ] **Step 1: Add helper tests for JSON-key upserts and backdating**

Append this test class:

```python
from datetime import timedelta

from django.utils import timezone

from ops.management.production_seed.common import SeedStats, backdate, upsert_json_key
from ops.models import Alert, AlertAction, Host


class ProductionSeedCommonTests(TestCase):
    def setUp(self):
        self.host = Host.objects.create(hostname='contract-host', ip_address='10.255.0.10')
        self.alert = Alert.objects.create(
            title='contract alert', level='warning', source='Prometheus',
            message='contract', host=self.host,
        )

    def test_json_seed_key_is_idempotent_and_backdatable(self):
        stats = SeedStats()
        action = upsert_json_key(
            AlertAction,
            json_field='metadata',
            seed_key='alert-action-contract-01',
            defaults={
                'alert': self.alert,
                'action': 'comment',
                'actor': 'SRE-王涛',
                'note': '确认依赖服务恢复',
                'metadata': {'source': 'alert-center'},
            },
            stats=stats,
        )
        same = upsert_json_key(
            AlertAction,
            json_field='metadata',
            seed_key='alert-action-contract-01',
            defaults={
                'alert': self.alert,
                'action': 'comment',
                'actor': 'SRE-王涛',
                'note': '确认依赖服务恢复',
                'metadata': {'source': 'alert-center'},
            },
            stats=stats,
        )
        target_time = timezone.now() - timedelta(days=9)
        backdate(AlertAction, action.pk, created_at=target_time)

        self.assertEqual(action.pk, same.pk)
        self.assertEqual(AlertAction.objects.count(), 1)
        self.assertEqual(AlertAction.objects.get().metadata['seed_key'], 'alert-action-contract-01')
        self.assertLess(AlertAction.objects.get().created_at, timezone.now() - timedelta(days=8))
        self.assertEqual(stats.created, 1)
        self.assertEqual(stats.updated, 1)
```

- [ ] **Step 2: Run the helper test and verify the import fails**

Run:

```powershell
docker compose exec -T sxdevops python manage.py test ops.test_seed_production_data.ProductionSeedCommonTests -v 2
```

Expected: FAIL because `ops.management.production_seed.common` does not exist.

- [ ] **Step 3: Implement the shared helper module**

Create `backend/ops/management/production_seed/__init__.py` as an empty package marker, then create `common.py` with these interfaces and behavior:

```python
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.utils import timezone

from ops.models import Alert, Host, K8sCluster, LogDataSource


@dataclass
class SeedStats:
    created: int = 0
    updated: int = 0

    def record(self, created):
        if created:
            self.created += 1
        else:
            self.updated += 1


def update_or_create_first(model, lookup, defaults, stats):
    obj = model.objects.filter(**lookup).order_by('pk').first()
    if obj is None:
        obj = model.objects.create(**lookup, **defaults)
        stats.record(True)
        return obj
    for field, value in defaults.items():
        setattr(obj, field, value)
    obj.save(update_fields=[*defaults.keys()])
    stats.record(False)
    return obj


def upsert_json_key(model, *, json_field, seed_key, defaults, stats):
    obj = model.objects.filter(**{f'{json_field}__seed_key': seed_key}).order_by('pk').first()
    payload = dict(defaults.get(json_field) or {})
    payload['seed_key'] = seed_key
    values = {**defaults, json_field: payload}
    if obj is None:
        obj = model.objects.create(**values)
        stats.record(True)
        return obj
    for field, value in values.items():
        setattr(obj, field, value)
    obj.save(update_fields=[*values.keys()])
    stats.record(False)
    return obj


def backdate(model, pk, **timestamps):
    model.objects.filter(pk=pk).update(**timestamps)


def resolve_base_objects(stats):
    user, created = get_user_model().objects.get_or_create(
        username='ops.reader',
        defaults={'first_name': '运维', 'last_name': '值班', 'is_active': True},
    )
    stats.record(created)
    host, created = Host.objects.update_or_create(
        hostname='order-api-ecs-01',
        defaults={
            'ip_address': '10.10.1.10', 'business_line': '交易平台',
            'environment': 'prod', 'admin_user': '应用运维-李俊',
            'os_type': 'Alibaba Cloud Linux 3', 'status': 'online',
            'cpu_usage': 43, 'memory_usage': 52, 'disk_usage': 61,
            'ssh_password': '',
        },
    )
    stats.record(created)
    alert = Alert.objects.order_by('pk').first()
    if alert is None:
        alert = Alert.objects.create(
            title='订单服务下游依赖延迟升高', level='critical', source='Prometheus',
            source_type='prometheus', message='库存依赖 P99 延迟连续五分钟超过阈值',
            host=host, service='order-service', environment='prod',
            fingerprint='prod-order-latency', last_received_at=timezone.now(),
        )
        stats.record(True)
    log_source, created = LogDataSource.objects.update_or_create(
        name='生产日志中心',
        defaults={
            'provider': 'loki', 'description': '生产应用与基础设施日志',
            'config': {'base_url': 'http://loki.ops.internal:3100'},
            'is_enabled': False, 'is_default': True,
        },
    )
    stats.record(created)
    cluster, created = K8sCluster.objects.update_or_create(
        name='prod-shanghai-k8s',
        defaults={
            'api_server': 'https://10.30.0.10:6443', 'kubeconfig': '',
            'status': 'disconnected', 'description': '交易平台生产集群',
        },
    )
    stats.record(created)
    return {'user': user, 'host': host, 'alert': alert, 'log_source': log_source, 'cluster': cluster}
```

- [ ] **Step 4: Implement the command shell**

Create `backend/ops/management/commands/seed_production_data.py`:

```python
from django.core.management.base import BaseCommand
from django.db import transaction

from ops.management.production_seed.common import SeedStats, resolve_base_objects
from ops.management.production_seed.task_resources import seed_task_resources
from ops.management.production_seed.alerting import seed_alerting
from ops.management.production_seed.observability import seed_observability
from ops.management.production_seed.aiops_data import seed_aiops


class Command(BaseCommand):
    help = '补充可重复执行的生产化样例数据，不删除现有记录'

    @transaction.atomic
    def handle(self, *args, **options):
        stats = SeedStats()
        base = resolve_base_objects(stats)
        task_context = seed_task_resources(stats, base)
        alert_context = seed_alerting(stats, base)
        obs_context = seed_observability(stats, base)
        seed_aiops(stats, base, task_context, alert_context, obs_context)
        self.stdout.write(self.style.SUCCESS(
            f'Production seed complete: created={stats.created}, updated={stats.updated}'
        ))
```

At this checkpoint, create the following minimal modules so the helper test can import the command while the next four tasks replace each function body:

```python
# backend/ops/management/production_seed/task_resources.py
def seed_task_resources(stats, base):
    return {}


# backend/ops/management/production_seed/alerting.py
def seed_alerting(stats, base):
    return {}


# backend/ops/management/production_seed/observability.py
def seed_observability(stats, base):
    return {}


# backend/ops/management/production_seed/aiops_data.py
def seed_aiops(stats, base, task_context, alert_context, obs_context):
    return None
```

- [ ] **Step 5: Run the helper test**

Run:

```powershell
docker compose exec -T sxdevops python manage.py test ops.test_seed_production_data.ProductionSeedCommonTests -v 2
```

Expected: PASS.

### Task 3: Populate the task resource tree

**Files:**

- Modify: `backend/ops/test_seed_production_data.py`
- Modify: `backend/ops/management/production_seed/task_resources.py`

- [ ] **Step 1: Add the task-resource contract test**

```python
from ops.models import TaskResource, TaskResourceGroup


class ProductionTaskResourceSeedTests(TestCase):
    def test_resource_tree_has_environments_systems_and_mixed_statuses(self):
        call_command('seed_production_data')
        self.assertEqual(TaskResourceGroup.objects.filter(group_type='environment').count(), 3)
        self.assertGreaterEqual(TaskResourceGroup.objects.filter(group_type='system').count(), 5)
        self.assertGreaterEqual(TaskResource.objects.count(), 18)
        self.assertTrue(TaskResource.objects.filter(resource_type='host', status='active').exists())
        self.assertTrue(TaskResource.objects.filter(resource_type='k8s', status='warning').exists())
        self.assertFalse(TaskResource.objects.exclude(ssh_password='').exists())
```

- [ ] **Step 2: Run the test and verify it fails on empty resources**

Run:

```powershell
docker compose exec -T sxdevops python manage.py test ops.test_seed_production_data.ProductionTaskResourceSeedTests -v 2
```

Expected: FAIL because the minimal resource seeder creates zero resource groups.

- [ ] **Step 3: Implement deterministic resource creation**

Replace the minimal resource function with logic using this exact matrix:

```python
from eventwall.models import EventEnvironment
from ops.models import TaskResource, TaskResourceGroup

from .common import update_or_create_first


ENVIRONMENTS = [
    ('生产环境', 'prod', 10),
    ('预发布环境', 'staging', 20),
    ('开发环境', 'dev', 30),
]
SYSTEMS = [
    ('交易平台', 'trade', 'prod', 10),
    ('支付平台', 'payment', 'prod', 20),
    ('会员中心', 'member', 'prod', 30),
    ('数据平台', 'data', 'prod', 40),
    ('基础设施', 'infra', 'prod', 50),
]
RESOURCE_NAMES = [
    'order-api-01', 'order-api-02', 'inventory-api-01', 'gateway-01',
    'payment-api-01', 'payment-worker-01', 'member-api-01', 'member-worker-01',
    'airflow-scheduler-01', 'airflow-worker-01', 'data-sync-01', 'report-api-01',
    'mysql-primary-01', 'mysql-replica-01', 'redis-cluster-01', 'mq-broker-01',
    'prod-order-workload', 'prod-payment-workload', 'staging-gateway-workload',
    'dev-data-workload',
]


def seed_task_resources(stats, base):
    event_envs = {item.code: item for item in EventEnvironment.objects.all()}
    envs = {}
    for name, code, order in ENVIRONMENTS:
        envs[code] = update_or_create_first(
            TaskResourceGroup,
            {'group_type': 'environment', 'parent': None, 'name': name},
            {
                'code': code, 'event_environment': event_envs.get(code),
                'description': f'{name}资源底座', 'sort_order': order,
                'created_by': 'ops.reader', 'updated_by': 'ops.reader',
            },
            stats,
        )
    systems = {}
    for name, code, env_code, order in SYSTEMS:
        systems[code] = update_or_create_first(
            TaskResourceGroup,
            {'group_type': 'system', 'parent': envs[env_code], 'name': name},
            {
                'code': code, 'description': f'{name}生产资源', 'sort_order': order,
                'created_by': 'ops.reader', 'updated_by': 'ops.reader',
            },
            stats,
        )
    for index, name in enumerate(RESOURCE_NAMES):
        is_k8s = index >= 16
        env_code = 'prod' if index < 18 else ('staging' if index == 18 else 'dev')
        system_code = ('trade', 'payment', 'member', 'data', 'infra')[index % 5]
        status = 'warning' if index in {10, 17} else ('inactive' if index == 15 else 'active')
        defaults = {
            'status': status,
            'ip_address': None if is_k8s else f'10.{10 + index // 8}.{1 + index % 8}.{20 + index}',
            'ssh_port': 22,
            'ssh_user': 'ops',
            'ssh_password': '',
            'cluster': base['cluster'] if is_k8s else None,
            'namespace': 'production' if env_code == 'prod' else env_code,
            'owner': ('应用运维-李俊', 'SRE-王涛', '数据平台-韩梅')[index % 3],
            'description': f'{name}运行资源',
            'metadata': {'region': 'cn-shanghai', 'zone': f'zone-{index % 3 + 1}'},
            'created_by': 'ops.reader',
            'updated_by': 'ops.reader',
        }
        update_or_create_first(
            TaskResource,
            {
                'name': name,
                'resource_type': 'k8s' if is_k8s else 'host',
                'environment': envs[env_code],
                'system': systems[system_code],
            },
            defaults,
            stats,
        )
    return {'environments': envs, 'systems': systems}
```

- [ ] **Step 4: Run the focused resource tests**

Run:

```powershell
docker compose exec -T sxdevops python manage.py test ops.test_seed_production_data.ProductionTaskResourceSeedTests -v 2
```

Expected: PASS with 3 environment groups, at least 5 system groups, and 20 resources.

### Task 4: Populate a safe alert notification and audit chain

**Files:**

- Modify: `backend/ops/test_seed_production_data.py`
- Modify: `backend/ops/management/production_seed/alerting.py`

- [ ] **Step 1: Add alerting assertions**

```python
from ops.models import (
    AlertAction, AlertMuteRule, AlertNotificationChannel, AlertNotificationLog,
    AlertNotificationRule, AlertRecipient, AlertRecipientGroup,
)


class ProductionAlertingSeedTests(TestCase):
    def test_alerting_chain_is_populated_without_live_channels(self):
        call_command('seed_production_data')
        self.assertGreaterEqual(AlertRecipient.objects.count(), 8)
        self.assertGreaterEqual(AlertRecipientGroup.objects.count(), 4)
        self.assertGreaterEqual(AlertNotificationChannel.objects.count(), 4)
        self.assertGreaterEqual(AlertNotificationRule.objects.count(), 5)
        self.assertGreaterEqual(AlertMuteRule.objects.count(), 2)
        self.assertGreaterEqual(AlertNotificationLog.objects.count(), 20)
        self.assertGreaterEqual(AlertAction.objects.count(), 15)
        self.assertFalse(AlertNotificationChannel.objects.filter(is_enabled=True).exists())
        self.assertFalse(AlertNotificationRule.objects.filter(is_enabled=True).exists())
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
docker compose exec -T sxdevops python manage.py test ops.test_seed_production_data.ProductionAlertingSeedTests -v 2
```

Expected: FAIL because alert contacts and histories remain empty.

- [ ] **Step 3: Implement alert topology and history**

Use `update_or_create_first` for objects keyed by names and `upsert_json_key` for history. Use these fixed inputs:

```python
RECIPIENTS = [
    ('王涛', 'SRE 值班负责人'), ('李俊', '交易平台应用运维'),
    ('周敏', '支付平台应用运维'), ('陈芳', '质量与发布保障'),
    ('韩梅', '数据平台运维'), ('赵磊', '数据库管理员'),
    ('孙博', '中间件运维'), ('吴迪', '安全响应工程师'),
]
GROUPS = {
    'SRE 一线值班': [0, 3], '交易平台值班': [1, 2],
    '数据平台值班': [4, 5], '基础设施值班': [0, 6, 7],
}
CHANNELS = [
    ('生产告警邮件', 'email', {'smtp_host': 'smtp.ops.internal', 'to': 'oncall@corp.internal'}),
    ('SRE 钉钉群', 'dingtalk', {'webhook_url': 'https://notify.ops.internal/dingtalk'}),
    ('应用值班飞书群', 'feishu', {'webhook_url': 'https://notify.ops.internal/feishu'}),
    ('基础设施企微群', 'wecom', {'webhook_url': 'https://notify.ops.internal/wecom'}),
]
RULES = [
    ('生产严重告警', 'critical', [{'key': 'environment', 'op': '=', 'value': 'prod'}], 0),
    ('交易平台告警', 'warning', [{'key': 'business_line', 'op': '=', 'value': '交易平台'}], 1),
    ('支付平台告警', 'warning', [{'key': 'service', 'op': '=~', 'value': 'payment.*'}], 1),
    ('数据平台告警', 'warning', [{'key': 'business_line', 'op': '=', 'value': '数据平台'}], 2),
    ('基础设施告警', 'warning', [{'key': 'resource_type', 'op': 'in', 'value': ['node', 'database']}], 3),
]
```

Implement the function with direct ORM writes only:

```python
from datetime import timedelta

from django.utils import timezone

from ops.models import (
    Alert, AlertAction, AlertAggregationRule, AlertEscalationPolicy,
    AlertMuteRule, AlertNotificationChannel, AlertNotificationLog,
    AlertNotificationRule, AlertRecipient, AlertRecipientGroup,
)

from .common import backdate, update_or_create_first, upsert_json_key


HISTORY_DAYS = [1, 2, 3, 4, 5, 6, 7, 9, 12, 15, 18, 21, 25, 30, 36, 45, 55, 65, 75, 88]


def seed_alerting(stats, base):
    recipients = []
    for index, (name, description) in enumerate(RECIPIENTS, start=1):
        recipients.append(update_or_create_first(
            AlertRecipient,
            {'name': name},
            {
                'phone': '', 'email': f'oncall{index}@corp.internal',
                'dingtalk_user_id': '', 'feishu_user_id': '', 'wecom_user_id': '',
                'is_enabled': True, 'description': description,
            },
            stats,
        ))

    groups = {}
    for name, indexes in GROUPS.items():
        group = update_or_create_first(
            AlertRecipientGroup,
            {'name': name},
            {'description': f'{name}告警响应组', 'is_enabled': True},
            stats,
        )
        group.recipients.set([recipients[index] for index in indexes])
        groups[name] = group

    channels = []
    for name, channel_type, config in CHANNELS:
        channels.append(update_or_create_first(
            AlertNotificationChannel,
            {'name': name, 'channel_type': channel_type},
            {
                'is_enabled': False, 'send_resolved': True, 'timeout_seconds': 8,
                'config': config, 'template_title': '[{{ level }}] {{ title }}',
                'template_body': '{{ message }}\n服务: {{ service }}\n环境: {{ environment }}',
            },
            stats,
        ))

    aggregation = AlertAggregationRule.objects.order_by('pk').first()
    escalation = AlertEscalationPolicy.objects.order_by('pk').first()
    rules = []
    group_values = list(groups.values())
    for index, (name, level, matchers, group_index) in enumerate(RULES):
        rule = update_or_create_first(
            AlertNotificationRule,
            {'name': name},
            {
                'is_enabled': False, 'matchers': matchers, 'min_level': level,
                'aggregation_rule': aggregation, 'escalation_policy': escalation,
                'notify_on_fire': True, 'notify_on_resolved': True,
                'notify_on_escalation': True, 'description': f'{name}分派策略',
            },
            stats,
        )
        rule.channels.set([channels[index % len(channels)]])
        rule.recipient_groups.set([group_values[group_index]])
        rules.append(rule)

    now = timezone.now()
    for name, matchers, days, reason in [
        ('生产数据库变更窗口', [{'key': 'resource_type', 'op': '=', 'value': 'database'}], 3, '主从切换与参数调整'),
        ('数据平台批处理窗口', [{'key': 'business_line', 'op': '=', 'value': '数据平台'}], 1, '月度批处理资源扩容'),
    ]:
        update_or_create_first(
            AlertMuteRule,
            {'name': name},
            {
                'is_enabled': True, 'matchers': matchers,
                'starts_at': now - timedelta(hours=2),
                'ends_at': now + timedelta(days=days),
                'reason': reason, 'created_by': 'SRE-王涛',
            },
            stats,
        )

    alerts = list(Alert.objects.order_by('pk')) or [base['alert']]
    notification_statuses = ['success', 'success', 'skipped', 'error']
    for index in range(20):
        status = notification_statuses[index % len(notification_statuses)]
        created_at = now - timedelta(days=HISTORY_DAYS[index], minutes=index * 7)
        log = upsert_json_key(
            AlertNotificationLog,
            json_field='request_payload',
            seed_key=f'notification-history-{index + 1:02d}',
            defaults={
                'alert': alerts[index % len(alerts)],
                'rule': rules[index % len(rules)],
                'channel': channels[index % len(channels)],
                'action': 'resolved' if index % 5 == 0 else 'fire',
                'status': status,
                'recipient_summary': group_values[index % len(group_values)].name,
                'request_payload': {'source': 'alert-center', 'attempt': index % 3 + 1},
                'response_body': 'accepted' if status == 'success' else '',
                'error_message': 'channel temporarily unavailable' if status == 'error' else '',
                'sent_at': created_at,
            },
            stats=stats,
        )
        backdate(AlertNotificationLog, log.pk, created_at=created_at)

    action_types = ['acknowledge', 'claim', 'comment', 'escalate', 'resolve', 'close']
    for index in range(15):
        action = upsert_json_key(
            AlertAction,
            json_field='metadata',
            seed_key=f'alert-action-history-{index + 1:02d}',
            defaults={
                'alert': alerts[index % len(alerts)],
                'action': action_types[index % len(action_types)],
                'actor': recipients[index % len(recipients)].name,
                'note': ('确认影响范围并开始处置', '补充链路与日志证据', '恢复后持续观察三十分钟')[index % 3],
                'metadata': {'source': 'alert-center', 'shift': 'primary' if index % 2 == 0 else 'backup'},
            },
            stats=stats,
        )
        backdate(AlertAction, action.pk, created_at=now - timedelta(days=HISTORY_DAYS[index]))

    return {'recipients': recipients, 'groups': groups, 'channels': channels, 'rules': rules}
```

Do not call notification services or model methods that send messages.

- [ ] **Step 4: Run focused alert tests**

Run:

```powershell
docker compose exec -T sxdevops python manage.py test ops.test_seed_production_data.ProductionAlertingSeedTests -v 2
```

Expected: PASS, with all seeded channels and rules disabled.

### Task 5: Populate observability configuration without connecting outward

**Files:**

- Modify: `backend/ops/test_seed_production_data.py`
- Modify: `backend/ops/management/production_seed/observability.py`

- [ ] **Step 1: Add observability assertions**

```python
from ops.models import GrafanaSetting, ObservabilityDataSourceLink, TracingDataSource


class ProductionObservabilitySeedTests(TestCase):
    def test_observability_catalog_is_populated_but_inactive(self):
        call_command('seed_production_data')
        self.assertEqual(MetricDataSource.objects.count(), 3)
        self.assertEqual(TracingDataSource.objects.count(), 2)
        self.assertGreaterEqual(ObservabilityDataSourceLink.objects.count(), 4)
        self.assertTrue(GrafanaSetting.objects.filter(name='default').exists())
        self.assertFalse(MetricDataSource.objects.filter(is_enabled=True).exists())
        self.assertFalse(TracingDataSource.objects.filter(is_enabled=True).exists())
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
docker compose exec -T sxdevops python manage.py test ops.test_seed_production_data.ProductionObservabilitySeedTests -v 2
```

Expected: FAIL because metric and tracing data sources are empty.

- [ ] **Step 3: Implement observability configuration**

Upsert this exact data using unique names:

```python
METRICS = [
    ('生产 Prometheus', 'prod', 'prod-shanghai', 'prometheus', 'http://prometheus.ops.internal:9090', True),
    ('长期指标存储', 'prod', 'global', 'victoriametrics', 'http://vmselect.ops.internal:8481', False),
    ('预发布 Prometheus', 'staging', 'staging-shanghai', 'prometheus', 'http://prometheus-staging.ops.internal:9090', False),
]
TRACING = [
    ('生产 Tempo', 'tempo', 'http://tempo.ops.internal:3200', True),
    ('预发布 Jaeger', 'jaeger', 'http://jaeger-staging.ops.internal:16686', False),
]
```

Implement the full seeder as follows:

```python
from ops.models import (
    GrafanaSetting, LogDataSource, MetricDataSource, ObservabilityDataSourceLink,
    TracingDataSource,
)

from .common import update_or_create_first


def seed_observability(stats, base):
    staging_log = update_or_create_first(
        LogDataSource,
        {'name': '预发布日志中心'},
        {
            'provider': 'loki', 'description': '预发布应用与基础设施日志',
            'config': {'base_url': 'http://loki-staging.ops.internal:3100'},
            'is_enabled': False, 'is_default': False,
        },
        stats,
    )
    log_sources = [base['log_source'], staging_log]
    metrics = []
    for name, environment, cluster_name, tsdb_type, url, is_default in METRICS:
        metrics.append(update_or_create_first(
            MetricDataSource,
            {'name': name},
            {
                'provider': 'prometheus', 'description': f'{environment} 指标查询入口',
                'environment': environment, 'cluster_name': cluster_name,
                'tsdb_type': tsdb_type, 'config': {'base_url': url, 'timeout_seconds': 8},
                'is_enabled': False, 'is_default': is_default,
            },
            stats,
        ))

    tracings = []
    for name, provider, url, is_default in TRACING:
        tracings.append(update_or_create_first(
            TracingDataSource,
            {'name': name},
            {
                'provider': provider, 'description': f'{name}链路检索入口',
                'config': {'base_url': url, 'timeout_seconds': 8},
                'is_enabled': False, 'is_default': is_default,
            },
            stats,
        ))

    links = []
    for log_index, log_source in enumerate(log_sources):
        for tracing_index, tracing in enumerate(tracings):
            link = update_or_create_first(
                ObservabilityDataSourceLink,
                {'log_datasource': log_source, 'tracing_datasource': tracing},
                {
                'name': f'{log_source.name}到{tracing.name}',
                'description': '日志、链路与看板上下文跳转',
                'is_enabled': False, 'is_default': log_index == 0 and tracing_index == 0,
                'log_to_trace_enabled': True, 'trace_to_log_enabled': True,
                'log_to_grafana_enabled': True, 'trace_to_grafana_enabled': True,
                'grafana_to_log_enabled': True, 'grafana_to_trace_enabled': True,
                'trace_id_fields': ['trace_id', 'traceId', 'trace.id'],
                'trace_id_regex': '(?i)[0-9a-f]{16,32}',
                'log_query_template': '{trace_id}',
                'log_label_mappings': [
                    {'source': 'service_name', 'target': 'service'},
                    {'source': 'environment', 'target': 'environment'},
                ],
                'grafana_dashboard_key': 'service-overview',
                'grafana_variable_mappings': [
                    {'source': 'service_name', 'target': 'service'},
                    {'source': 'environment', 'target': 'env'},
                ],
                'span_start_shift': '-5m', 'span_end_shift': '5m',
                'window_minutes': 10,
                },
                stats,
            )
            links.append(link)

    grafana = update_or_create_first(
        GrafanaSetting,
        {'name': 'default'},
        {
            'enabled': False, 'url': 'http://grafana.ops.internal:3000',
            'default_path': '/d/service-overview',
            'folders': [
                {'key': 'applications', 'name': '应用监控'},
                {'key': 'infrastructure', 'name': '基础设施'},
            ],
            'dashboards': [
                {'key': 'service-overview', 'name': '服务总览', 'path': '/d/service-overview', 'folder_key': 'applications'},
                {'key': 'k8s-cluster', 'name': 'Kubernetes 集群', 'path': '/d/k8s-cluster', 'folder_key': 'infrastructure'},
                {'key': 'database-health', 'name': '数据库健康度', 'path': '/d/database-health', 'folder_key': 'infrastructure'},
            ],
            'updated_by': 'ops.reader',
        },
        stats,
    )
    return {'log_sources': log_sources, 'metrics': metrics, 'tracings': tracings, 'links': links, 'grafana': grafana}
```

- [ ] **Step 4: Run focused observability tests**

Run:

```powershell
docker compose exec -T sxdevops python manage.py test ops.test_seed_production_data.ProductionObservabilitySeedTests -v 2
```

Expected: PASS without DNS, HTTP, database, or tracing connection attempts.

### Task 6: Populate AIOps knowledge and audit history

**Files:**

- Modify: `backend/ops/test_seed_production_data.py`
- Modify: `backend/ops/management/production_seed/aiops_data.py`

- [ ] **Step 1: Add AIOps coverage assertions**

```python
from aiops.models import (
    AIOpsChatMessage, AIOpsChatSession, AIOpsExternalTask,
    AIOpsModelInvocation, AIOpsPendingAction, AIOpsReviewKnowledge,
    AIOpsRunbook, AIOpsRunbookVersion, AIOpsToolInvocation,
)


class ProductionAIOpsSeedTests(TestCase):
    def test_aiops_history_and_knowledge_are_populated(self):
        call_command('seed_production_data')
        self.assertGreaterEqual(AIOpsChatSession.objects.count(), 8)
        self.assertGreaterEqual(AIOpsChatMessage.objects.count(), 16)
        self.assertGreaterEqual(AIOpsToolInvocation.objects.count(), 30)
        self.assertGreaterEqual(AIOpsModelInvocation.objects.count(), 24)
        self.assertGreaterEqual(AIOpsPendingAction.objects.count(), 8)
        self.assertGreaterEqual(AIOpsExternalTask.objects.count(), 6)
        self.assertGreaterEqual(AIOpsRunbook.objects.count(), 6)
        self.assertGreaterEqual(AIOpsRunbookVersion.objects.count(), 6)
        self.assertGreaterEqual(AIOpsReviewKnowledge.objects.count(), 8)
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
docker compose exec -T sxdevops python manage.py test ops.test_seed_production_data.ProductionAIOpsSeedTests -v 2
```

Expected: FAIL because audit, task, Runbook, and review collections are empty.

- [ ] **Step 3: Implement deterministic AIOps records**

Use these exact topics as stable business keys:

```python
TOPICS = [
    ('订单接口 P99 延迟升高分析', 'order-service', 'prod'),
    ('支付任务积压根因定位', 'payment-worker', 'prod'),
    ('会员服务发布健康检查失败', 'member-api', 'prod'),
    ('数据库连接池耗尽排查', 'mysql-primary', 'prod'),
    ('数据同步任务延迟分析', 'data-sync', 'prod'),
    ('Kubernetes 节点磁盘压力处理', 'k8s-node', 'prod'),
    ('网关错误率异常分析', 'gateway', 'staging'),
    ('Redis 热点 Key 容量评估', 'redis-cluster', 'prod'),
]
TOOL_NAMES = ['query_alerts', 'search_logs', 'get_host_detail', 'query_metrics']
MODEL_PURPOSES = ['chat_planning', 'answer_formatting', 'parameter_extraction']
ACTION_STATUSES = ['pending', 'confirmed', 'executed', 'canceled', 'failed', 'executed', 'confirmed', 'pending']
TASK_STATUSES = ['completed', 'running', 'failed', 'canceled', 'completed', 'queued', 'completed', 'failed']
```

Implement the exact stable-key and relationship rules below:

```python
from datetime import timedelta
from decimal import Decimal
import uuid

from django.utils import timezone

from aiops.models import (
    AIOpsChatMessage, AIOpsChatSession, AIOpsExternalTask,
    AIOpsKnowledgeEnvironment, AIOpsModelInvocation, AIOpsModelProvider,
    AIOpsPendingAction, AIOpsReviewKnowledge, AIOpsRunbook,
    AIOpsRunbookVersion, AIOpsToolInvocation,
)

from .common import backdate, update_or_create_first, upsert_json_key


HISTORY_DAYS = [1, 2, 3, 5, 7, 14, 30, 75]
RUNBOOK_SPECS = [
    ('order-latency-response', '订单接口延迟应急处置', 'order-service'),
    ('payment-backlog-recovery', '支付任务积压恢复', 'payment-worker'),
    ('member-release-rollback', '会员服务发布回滚', 'member-api'),
    ('mysql-pool-exhaustion', '数据库连接池耗尽处置', 'mysql-primary'),
    ('k8s-disk-pressure', 'Kubernetes 节点磁盘压力处置', 'k8s-node'),
    ('redis-hot-key-capacity', 'Redis 热点 Key 容量治理', 'redis-cluster'),
]


def seed_aiops(stats, base, task_context, alert_context, obs_context):
    now = timezone.now()
    provider = AIOpsModelProvider.objects.order_by('pk').first()
    if provider is None:
        provider = update_or_create_first(
            AIOpsModelProvider,
            {'name': '平台分析模型'},
            {
                'provider_type': 'openai_compatible',
                'base_url': 'http://model-gateway.ops.internal/v1',
                'default_model': 'ops-reasoner-32b', 'backup_model': '',
                'temperature': 0.2, 'max_tokens': 10000, 'timeout_seconds': 30,
                'price_currency': 'USD', 'input_token_price_per_1m': Decimal('0.600000'),
                'output_token_price_per_1m': Decimal('2.400000'),
                'is_enabled': False, 'last_test_status': 'unknown',
                'last_test_message': '',
            },
            stats,
        )

    environment_specs = [
        ('生产交易平台', ['prod', 'production'], 'prod'),
        ('预发布交易平台', ['staging', 'pre'], 'staging'),
        ('生产数据平台', ['data-prod', 'prod-data'], 'prod'),
    ]
    env_groups = task_context['environments']
    knowledge_envs = []
    for index, (name, aliases, env_code) in enumerate(environment_specs):
        knowledge_envs.append(update_or_create_first(
            AIOpsKnowledgeEnvironment,
            {'name': name},
            {
                'aliases': aliases, 'description': f'{name}资源与可观测上下文',
                'event_environments': [env_code],
                'grafana_folder_keys': ['applications', 'infrastructure'],
                'metric_datasource_ids': [item.pk for item in obs_context['metrics'] if item.environment == env_code],
                'log_datasource_ids': [item.pk for item in obs_context['log_sources']],
                'tracing_datasource_ids': [item.pk for item in obs_context['tracings']],
                'observability_link_ids': [item.pk for item in obs_context['links']],
                'alert_environments': [env_code],
                'k8s_cluster_ids': [base['cluster'].pk],
                'k8s_namespaces': {str(base['cluster'].pk): ['production' if env_code == 'prod' else env_code]},
                'docker_host_ids': [],
                'task_resource_environment_ids': [env_groups[env_code].pk],
                'association_snapshot': {'services': [topic[1] for topic in TOPICS if topic[2] == env_code]},
                'child_node_snapshot': {'systems': list(task_context['systems'].keys())},
                'snapshot_generated_at': now,
                'is_default': index == 0, 'is_enabled': True,
                'created_by': 'ops.reader', 'updated_by': 'ops.reader',
            },
            stats,
        ))

    sessions = []
    assistant_messages = []
    for session_index, (title, service, environment) in enumerate(TOPICS):
        event_time = now - timedelta(days=HISTORY_DAYS[session_index], hours=session_index)
        session = upsert_json_key(
            AIOpsChatSession,
            json_field='context',
            seed_key=f'aiops-session-{session_index + 1:02d}',
            defaults={
                'user': base['user'], 'title': title,
                'status': 'active' if session_index < 2 else 'archived',
                'last_message_at': event_time + timedelta(minutes=20),
                'context': {'service': service, 'environment': environment, 'source': 'operations-console'},
            },
            stats=stats,
        )
        backdate(AIOpsChatSession, session.pk, created_at=event_time, updated_at=event_time + timedelta(minutes=20))
        user_message = upsert_json_key(
            AIOpsChatMessage,
            json_field='metadata',
            seed_key=f'aiops-message-{session_index + 1:02d}-user',
            defaults={
                'session': session, 'role': 'user', 'message_type': 'text',
                'content': f'请分析 {title}，给出影响范围、证据和处置建议。',
                'citations': [], 'tool_calls': [],
                'metadata': {'service': service, 'environment': environment},
            },
            stats=stats,
        )
        backdate(AIOpsChatMessage, user_message.pk, created_at=event_time)
        assistant = upsert_json_key(
            AIOpsChatMessage,
            json_field='metadata',
            seed_key=f'aiops-message-{session_index + 1:02d}-assistant',
            defaults={
                'session': session, 'role': 'assistant', 'message_type': 'analysis',
                'content': f'已完成 {service} 的告警、日志、指标与变更关联分析，建议按 Runbook 分阶段处置并持续观察。',
                'citations': [{'type': 'alert', 'id': base['alert'].pk}],
                'tool_calls': TOOL_NAMES,
                'metadata': {'service': service, 'environment': environment, 'confidence': 0.86},
            },
            stats=stats,
        )
        backdate(AIOpsChatMessage, assistant.pk, created_at=event_time + timedelta(minutes=20))

        for tool_index, tool_name in enumerate(TOOL_NAMES):
            failed = (session_index + tool_index) % 9 == 0
            invocation = upsert_json_key(
                AIOpsToolInvocation,
                json_field='request_payload',
                seed_key=f'aiops-tool-{session_index + 1:02d}-{tool_index + 1:02d}',
                defaults={
                    'session': session, 'message': assistant, 'tool_name': tool_name,
                    'status': 'failed' if failed else 'success',
                    'latency_ms': 140 + session_index * 35 + tool_index * 70,
                    'request_payload': {'service': service, 'environment': environment},
                    'response_summary': {'matched': 0 if failed else 6 + session_index, 'error': 'upstream timeout' if failed else ''},
                },
                stats=stats,
            )
            backdate(AIOpsToolInvocation, invocation.pk, created_at=event_time + timedelta(minutes=2 + tool_index * 2))

        for purpose_index, purpose in enumerate(MODEL_PURPOSES):
            failed = (session_index + purpose_index) % 11 == 0
            prompt_tokens = 900 + session_index * 80
            completion_tokens = 260 + purpose_index * 60
            total_tokens = prompt_tokens + completion_tokens
            invocation = upsert_json_key(
                AIOpsModelInvocation,
                json_field='request_summary',
                seed_key=f'aiops-model-{session_index + 1:02d}-{purpose_index + 1:02d}',
                defaults={
                    'provider': provider, 'session': session, 'message': assistant,
                    'username': base['user'].username, 'purpose': purpose,
                    'requested_model': provider.default_model or 'ops-reasoner-32b',
                    'resolved_model': provider.default_model or 'ops-reasoner-32b',
                    'status': 'failed' if failed else 'success',
                    'latency_ms': 820 + session_index * 95 + purpose_index * 180,
                    'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens,
                    'total_tokens': total_tokens,
                    'estimated_cost_usd': (Decimal(total_tokens) * Decimal('0.000002')).quantize(Decimal('0.000001')),
                    'estimated_cost_currency': 'USD',
                    'request_summary': {'service': service, 'environment': environment},
                    'response_summary': {
                        'finish_reason': 'error' if failed else 'stop',
                        'error_type': ('rate_limited' if session_index % 2 == 0 else 'timeout') if failed else '',
                    },
                },
                stats=stats,
            )
            backdate(AIOpsModelInvocation, invocation.pk, created_at=event_time + timedelta(minutes=10 + purpose_index * 2))

        action = upsert_json_key(
            AIOpsPendingAction,
            json_field='action_payload',
            seed_key=f'aiops-action-{session_index + 1:02d}',
            defaults={
                'session': session, 'message': assistant,
                'action_type': 'execute_host_task',
                'title': f'{service} 诊断与恢复任务',
                'risk_level': ('low', 'medium', 'high', 'critical')[session_index % 4],
                'status': ACTION_STATUSES[session_index],
                'action_payload': {'operation': 'diagnose_service', 'service': service, 'environment': environment},
                'result_payload': (
                    {'summary': '任务步骤已记录'} if ACTION_STATUSES[session_index] == 'executed'
                    else {'error_type': 'policy_blocked'} if ACTION_STATUSES[session_index] == 'failed'
                    else {}
                ),
                'confirmed_by': 'SRE-王涛' if ACTION_STATUSES[session_index] in {'confirmed', 'executed'} else '',
                'confirmed_at': event_time + timedelta(minutes=22) if ACTION_STATUSES[session_index] in {'confirmed', 'executed'} else None,
            },
            stats=stats,
        )
        backdate(AIOpsPendingAction, action.pk, created_at=event_time + timedelta(minutes=21), updated_at=event_time + timedelta(minutes=22))
        sessions.append(session)
        assistant_messages.append(assistant)

    tasks = []
    for index, (title, service, environment) in enumerate(TOPICS):
        public_id = uuid.uuid5(uuid.NAMESPACE_URL, f'ai-ops-production-task-{index}')
        task, created = AIOpsExternalTask.objects.update_or_create(
            public_id=public_id,
            defaults={
                'source_agent': 'incident-analysis-agent', 'title': title,
                'action_code': 'incident_analysis', 'agent_mode': 'orchestrated',
                'status': TASK_STATUSES[index],
                'input_payload': {'service': service, 'environment': environment},
                'plan_steps': ['收集告警', '检索日志与指标', '分析变更', '生成处置建议'],
                'orchestration_state': {'current_step': 4 if TASK_STATUSES[index] == 'completed' else 2},
                'agent_results': [{'agent': 'observability', 'status': 'success'}],
                'react_trace': [{'thought': '关联最近变更与异常窗口', 'action': 'query_context'}],
                'result_payload': {'summary': '分析完成'} if TASK_STATUSES[index] == 'completed' else {},
                'error_message': '上下文查询超时' if TASK_STATUSES[index] == 'failed' else '',
                'created_by': base['user'],
                'completed_at': now - timedelta(days=HISTORY_DAYS[index]) if TASK_STATUSES[index] == 'completed' else None,
                'canceled_at': now - timedelta(days=HISTORY_DAYS[index]) if TASK_STATUSES[index] == 'canceled' else None,
            },
        )
        stats.record(created)
        backdate(AIOpsExternalTask, task.pk, created_at=now - timedelta(days=HISTORY_DAYS[index]), updated_at=now - timedelta(days=HISTORY_DAYS[index]))
        tasks.append(task)

    runbooks = []
    for index, (slug, title, service) in enumerate(RUNBOOK_SPECS):
        runbook, created = AIOpsRunbook.objects.update_or_create(
            slug=slug,
            defaults={
                'title': title, 'environment': 'prod', 'service': service,
                'status': 'published', 'version': 1,
                'content': '1. 确认影响范围\n2. 保存现场证据\n3. 执行最小风险处置\n4. 验证核心指标\n5. 持续观察并复盘',
                'evidence': [{'type': 'alert', 'id': base['alert'].pk}],
                'tags': ['incident', 'operations', service],
                'source_refs': [{'type': 'session', 'id': sessions[index % len(sessions)].pk}],
                'source_task': tasks[index % len(tasks)],
                'source_session': sessions[index % len(sessions)],
                'created_by': 'SRE-王涛', 'updated_by': 'SRE-王涛',
                'published_at': now - timedelta(days=HISTORY_DAYS[index]),
                'archived_at': None,
            },
        )
        stats.record(created)
        _, version_created = AIOpsRunbookVersion.objects.update_or_create(
            runbook=runbook,
            version=1,
            defaults={
                'status': 'published', 'title': title, 'content': runbook.content,
                'evidence': runbook.evidence, 'tags': runbook.tags,
                'source_refs': runbook.source_refs,
                'change_note': '建立标准处置流程', 'created_by': 'SRE-王涛',
            },
        )
        stats.record(version_created)
        runbooks.append(runbook)

    for index, (title, service, environment) in enumerate(TOPICS):
        review, created = AIOpsReviewKnowledge.objects.update_or_create(
            slug=f'review-{index + 1:02d}',
            defaults={
                'title': f'{title}复盘',
                'summary': f'{service} 异常由容量波动与下游依赖延迟共同触发，已完成处置并补充监控。',
                'environment': environment, 'service': service,
                'source_type': 'session',
                'evidence': [{'type': 'alert', 'id': base['alert'].pk}],
                'tags': ['postmortem', service, environment],
                'source_refs': [{'type': 'external_task', 'id': str(tasks[index].public_id)}],
                'source_session': sessions[index], 'source_task': tasks[index],
                'source_runbook': runbooks[index % len(runbooks)],
                'created_by': 'SRE-王涛', 'updated_by': 'SRE-王涛',
            },
        )
        stats.record(created)
        backdate(AIOpsReviewKnowledge, review.pk, created_at=now - timedelta(days=HISTORY_DAYS[index]), updated_at=now - timedelta(days=HISTORY_DAYS[index]))
```

- [ ] **Step 4: Run the focused AIOps tests**

Run:

```powershell
docker compose exec -T sxdevops python manage.py test ops.test_seed_production_data.ProductionAIOpsSeedTests -v 2
```

Expected: PASS with all minimum counts satisfied.

### Task 7: Prove idempotency, preservation, and network safety

**Files:**

- Modify: `backend/ops/test_seed_production_data.py`

- [ ] **Step 1: Add integration safety tests**

```python
from unittest.mock import patch

from aiops.models import AIOpsToolInvocation
from ops.models import AlertNotificationLog, Host, ObservabilityDataSourceLink, TaskResource


class ProductionSeedSafetyTests(TestCase):
    def test_second_run_keeps_counts_and_preserves_existing_host(self):
        existing = Host.objects.create(hostname='customer-owned-host', ip_address='10.254.0.9')
        call_command('seed_production_data')
        before = {
            'resources': TaskResource.objects.count(),
            'notifications': AlertNotificationLog.objects.count(),
            'links': ObservabilityDataSourceLink.objects.count(),
            'tools': AIOpsToolInvocation.objects.count(),
        }

        call_command('seed_production_data')

        after = {
            'resources': TaskResource.objects.count(),
            'notifications': AlertNotificationLog.objects.count(),
            'links': ObservabilityDataSourceLink.objects.count(),
            'tools': AIOpsToolInvocation.objects.count(),
        }
        self.assertEqual(before, after)
        self.assertTrue(Host.objects.filter(pk=existing.pk).exists())

    @patch('requests.sessions.Session.request', side_effect=AssertionError('external HTTP is forbidden'))
    def test_command_does_not_issue_http_requests(self, _request):
        call_command('seed_production_data')
```

- [ ] **Step 2: Run the complete command test module**

Run:

```powershell
docker compose exec -T sxdevops python manage.py test ops.test_seed_production_data -v 2
```

Expected: all tests PASS; running the command twice leaves counts unchanged.

- [ ] **Step 3: Run Django checks and focused regression tests**

Run:

```powershell
docker compose exec -T sxdevops python manage.py check
docker compose exec -T sxdevops python manage.py test ops.tests.AlertActionApiTests aiops.tests eventwall.tests -v 1
```

Expected: `System check identified no issues`; focused tests PASS. If `aiops.tests` contains a pre-existing failure, record the exact failing test and prove the new command module still passes independently before changing unrelated production code.

### Task 8: Make population survive Docker container recreation

**Files:**

- Modify: `docker/entrypoint.sh`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add a startup-order test by inspection**

Run before editing:

```powershell
rg -n "SEED_PRODUCTION|seed_production_data" docker\entrypoint.sh docker-compose.yml
```

Expected: no matches.

- [ ] **Step 2: Invoke the additive seed after the destructive base seed**

Insert this block in `docker/entrypoint.sh` immediately after the existing `SXDEVOPS_SEED_DATA` block and before the template seed block:

```sh
if [ "${SXDEVOPS_SEED_PRODUCTION_DATA:-1}" = "1" ]; then
  python manage.py seed_production_data
fi
```

Add this environment value next to the existing seed flags under the `sxdevops` service:

```yaml
      SXDEVOPS_SEED_PRODUCTION_DATA: "1"
```

- [ ] **Step 3: Verify ordering and Compose syntax**

Run:

```powershell
rg -n "SXDEVOPS_SEED_DATA|SXDEVOPS_SEED_PRODUCTION_DATA|seed_data|seed_production_data" docker\entrypoint.sh docker-compose.yml
docker compose config --quiet
```

Expected: the entrypoint calls `seed_data` first and `seed_production_data` second; Compose validation exits 0.

### Task 9: Apply, audit APIs, and visually verify pages

**Files:**

- No source changes

- [ ] **Step 1: Rebuild and start the service**

Because Docker Desktop is owned by the interactive Windows account, run in the user's terminal if the Codex sandbox cannot access the named pipe:

```powershell
Set-Location -LiteralPath 'C:\Users\sunyupeng\PycharmProjects\AI Ops'
docker compose up -d --build
docker compose ps
```

Expected: `sxdevops-app`, `sxdevops-mysql`, and `sxdevops-redis` are running; MySQL and Redis report healthy.

- [ ] **Step 2: Run the command twice and capture counts**

```powershell
docker compose exec -T sxdevops python manage.py seed_production_data
docker compose exec -T sxdevops python manage.py seed_production_data
```

Expected: both commands end with `Production seed complete`; the second run reports updates but no duplicate-key errors.

- [ ] **Step 3: Audit all target GET endpoints**

Authenticate at `POST http://localhost:8000/api/auth/login/`, send `Authorization: Token <token>`, and verify HTTP 200 with non-zero counts for:

```text
/api/task-resource-groups/
/api/task-resources/
/api/alert-recipients/
/api/alert-recipient-groups/
/api/alert-notification-channels/
/api/alert-notification-rules/
/api/alert-mute-rules/
/api/alert-notification-logs/
/api/alert-actions/
/api/observability/datasource-links/
/api/observability/tracing/datasources/
/api/observability/metric/datasources/
/api/aiops/knowledge-environments/
/api/aiops/admin/audit/tool-invocations/
/api/aiops/admin/audit/model-invocations/
/api/aiops/admin/audit/actions/
/api/aiops/a2a/tasks/
/api/aiops/runbooks/
/api/aiops/review-knowledge/
```

Expected: every listed endpoint returns 200 and a positive collection count.

- [ ] **Step 4: Verify browser pages**

Open `http://localhost:8000`, log in, and inspect:

```text
/tasks/resources
/alerts
/observability/metrics?tab=datasources
/observability/tracing?tab=datasources
/observability/datasource-links
/aiops/knowledge
/aiops/audit
```

Expected: lists, statistics, filters, and history tables render records; no target view shows an empty-state panel because its backing collection is empty.

- [ ] **Step 5: Final health and preservation check**

Run:

```powershell
docker compose ps
docker compose logs --tail 100 sxdevops
```

Expected: the application remains running without traceback, seed errors, outbound notification attempts, or connection-test traffic. Existing host, deployment, log, SQL audit, and event-wall collections remain non-empty.
