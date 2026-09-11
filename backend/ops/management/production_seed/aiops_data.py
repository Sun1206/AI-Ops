from datetime import timedelta
from decimal import Decimal
import uuid

from django.utils import timezone

from aiops.models import (
    AIOpsChatMessage,
    AIOpsChatSession,
    AIOpsExternalTask,
    AIOpsKnowledgeEnvironment,
    AIOpsModelInvocation,
    AIOpsModelProvider,
    AIOpsPendingAction,
    AIOpsReviewKnowledge,
    AIOpsRunbook,
    AIOpsRunbookVersion,
    AIOpsToolInvocation,
)

from .common import backdate, get_or_create_first, get_or_create_json_key


TOPICS = [
    ('订单接口 P99 延迟升高分析', 'order-service', 'prod'),
    ('支付任务积压根因定位', 'payment-worker', 'prod'),
    ('会员服务发布健康检查失败', 'member-api', 'prod'),
    ('数据库连接池耗尽排查', 'mysql-primary', 'prod'),
    ('数据同步任务延迟分析', 'data-sync', 'prod'),
    ('Kubernetes 节点磁盘压力处理', 'k8s-node', 'prod'),
    ('网关错误率异常分析', 'gateway', 'staging'),
    ('Redis 热点 Key 容量评估', 'redis-cluster', 'prod'),
    ('订单数据库主从延迟排查', 'order-db', 'prod'),
    ('支付网关证书到期风险评估', 'payment-gateway', 'prod'),
    ('搜索服务内存增长趋势分析', 'search-service', 'prod'),
    ('消息队列消费延迟恢复', 'kafka-consumer', 'prod'),
    ('对象存储访问错误定位', 'storage-proxy', 'prod'),
    ('风控规则发布后错误率分析', 'risk-engine', 'prod'),
    ('预发布环境镜像拉取失败', 'image-registry', 'staging'),
    ('核心 DNS 解析抖动排查', 'core-dns', 'prod'),
]

TOOL_NAMES = ['query_alerts', 'search_logs', 'get_host_detail', 'query_metrics']
MODEL_PURPOSES = ['chat_planning', 'answer_formatting', 'parameter_extraction']
ACTION_STATUSES = [
    'pending', 'confirmed', 'executed', 'canceled',
    'failed', 'executed', 'confirmed', 'pending',
] * 2
TASK_STATUSES = [
    'completed', 'running', 'failed', 'canceled',
    'completed', 'queued', 'completed', 'failed',
] * 2
HISTORY_DAYS = [0, 1, 2, 3, 4, 5, 6, 7, 9, 11, 13, 15, 18, 21, 25, 29]

RUNBOOK_SPECS = [
    ('order-latency-response', '订单接口延迟应急处置', 'order-service'),
    ('payment-backlog-recovery', '支付任务积压恢复', 'payment-worker'),
    ('member-release-rollback', '会员服务发布回滚', 'member-api'),
    ('mysql-pool-exhaustion', '数据库连接池耗尽处置', 'mysql-primary'),
    ('k8s-disk-pressure', 'Kubernetes 节点磁盘压力处置', 'k8s-node'),
    ('redis-hot-key-capacity', 'Redis 热点 Key 容量治理', 'redis-cluster'),
]


def _resolve_provider(stats):
    expected = {
        'provider_type': 'openai_compatible',
        'base_url': 'http://model-gateway.ops.internal/v1',
        'default_model': 'ops-reasoner-32b',
        'is_enabled': False,
    }
    provider = get_or_create_first(
        AIOpsModelProvider,
        {'name': 'AI Ops 智能分析模型'},
        {
            **expected,
            'backup_model': '',
            'temperature': 0.2,
            'max_tokens': 10000,
            'timeout_seconds': 30,
            'price_currency': 'USD',
            'input_token_price_per_1m': Decimal('0.600000'),
            'output_token_price_per_1m': Decimal('2.400000'),
            'is_enabled': False,
            'last_test_status': 'unknown',
            'last_test_message': '',
        },
        stats,
    )
    if all(getattr(provider, field) == value for field, value in expected.items()):
        return provider
    # A same-name user provider is never reused for generated invocation history.
    return None


def _seed_knowledge_environments(stats, base, task_context, obs_context, now):
    environment_specs = [
        ('生产交易平台', ['prod', 'production'], 'prod'),
        ('预发布交易平台', ['staging', 'pre'], 'staging'),
        ('生产数据平台', ['data-prod', 'prod-data'], 'prod'),
    ]
    env_groups = task_context['environments']
    knowledge_envs = []
    for index, (name, aliases, env_code) in enumerate(environment_specs):
        knowledge_envs.append(get_or_create_first(
            AIOpsKnowledgeEnvironment,
            {'name': name},
            {
                'aliases': aliases,
                'description': f'{name}资源与可观测上下文',
                'event_environments': [env_code],
                'grafana_folder_keys': ['applications', 'infrastructure'],
                'metric_datasource_ids': [
                    item.pk for item in obs_context['metrics']
                    if item.environment == env_code
                ],
                'log_datasource_ids': [item.pk for item in obs_context['log_sources']],
                'tracing_datasource_ids': [item.pk for item in obs_context['tracings']],
                'observability_link_ids': [item.pk for item in obs_context['links']],
                'alert_environments': [env_code],
                'k8s_cluster_ids': [base['cluster'].pk],
                'k8s_namespaces': {
                    str(base['cluster'].pk): [
                        'production' if env_code == 'prod' else env_code
                    ]
                },
                'docker_host_ids': [],
                'task_resource_environment_ids': [env_groups[env_code].pk],
                'association_snapshot': {
                    'services': [topic[1] for topic in TOPICS if topic[2] == env_code]
                },
                'child_node_snapshot': {'systems': list(task_context['systems'])},
                'snapshot_generated_at': now,
                'is_default': index == 0,
                'is_enabled': True,
                'created_by': 'ops.reader',
                'updated_by': 'ops.reader',
            },
            stats,
        ))
    return knowledge_envs


def _seed_sessions_and_audit(stats, base, provider, now):
    sessions = []
    for session_index, (title, service, environment) in enumerate(TOPICS):
        event_time = now - timedelta(
            days=HISTORY_DAYS[session_index],
            hours=session_index,
        )
        session = get_or_create_json_key(
            AIOpsChatSession,
            json_field='context',
            seed_key=f'aiops-session-{session_index + 1:02d}',
            defaults={
                'user': base['user'],
                'title': title,
                'status': 'active' if session_index < 2 else 'archived',
                'last_message_at': event_time + timedelta(minutes=20),
                'context': {
                    'service': service,
                    'environment': environment,
                    'source': 'operations-console',
                    'seed_namespace': 'production-sessions',
                },
            },
            stats=stats,
        )
        session_context = dict(session.context or {})
        if (
            session_context.get('seed_key') == f'aiops-session-{session_index + 1:02d}'
            and session_context.get('seed_namespace') != 'production-sessions'
        ):
            session_context['seed_namespace'] = 'production-sessions'
            session.context = session_context
            session.save(update_fields=['context'])
        backdate(
            session,
            created_at=event_time,
            updated_at=event_time + timedelta(minutes=20),
        )
        user_message = get_or_create_json_key(
            AIOpsChatMessage,
            json_field='metadata',
            seed_key=f'aiops-message-{session_index + 1:02d}-user',
            defaults={
                'session': session,
                'role': 'user',
                'message_type': 'text',
                'content': f'请分析 {title}，给出影响范围、证据和处置建议。',
                'citations': [],
                'tool_calls': [],
                'metadata': {'service': service, 'environment': environment},
            },
            stats=stats,
        )
        backdate(user_message, created_at=event_time)

        assistant = get_or_create_json_key(
            AIOpsChatMessage,
            json_field='metadata',
            seed_key=f'aiops-message-{session_index + 1:02d}-assistant',
            defaults={
                'session': session,
                'role': 'assistant',
                'message_type': 'analysis',
                'content': (
                    f'已完成 {service} 的告警、日志、指标与变更关联分析，'
                    '建议按 Runbook 分阶段处置并持续观察。'
                ),
                'citations': [{'type': 'alert', 'id': base['alert'].pk}],
                'tool_calls': TOOL_NAMES,
                'metadata': {
                    'service': service,
                    'environment': environment,
                    'confidence': 0.86,
                },
            },
            stats=stats,
        )
        backdate(
            assistant,
            created_at=event_time + timedelta(minutes=20),
        )

        conversation_turns = [
            (
                'followup-user', 'user', 'text',
                '请补充最近变更、异常主机和关键日志证据。',
                [],
            ),
            (
                'followup-assistant', 'assistant', 'analysis',
                f'最近变更与异常窗口重合，{service} 的两台实例出现资源抖动，'
                '日志中已定位到同一批请求链路，建议先隔离异常实例并观察核心指标。',
                TOOL_NAMES[:3],
            ),
            (
                'action-user', 'user', 'text',
                '给出可以执行的低风险步骤，并说明验证标准。',
                [],
            ),
            (
                'action-assistant', 'assistant', 'action',
                '已生成分阶段处置方案：保存现场、隔离异常实例、恢复流量，'
                '以错误率、P99 延迟和队列积压恢复到基线作为验证标准。',
                ['create_pending_action'],
            ),
        ]
        for turn_index, (suffix, role, message_type, content, tool_calls) in enumerate(
            conversation_turns,
            start=1,
        ):
            message = get_or_create_json_key(
                AIOpsChatMessage,
                json_field='metadata',
                seed_key=f'aiops-message-{session_index + 1:02d}-{suffix}',
                defaults={
                    'session': session,
                    'role': role,
                    'message_type': message_type,
                    'content': content,
                    'citations': (
                        [{'type': 'alert', 'id': base['alert'].pk}]
                        if role == 'assistant' else []
                    ),
                    'tool_calls': tool_calls,
                    'metadata': {
                        'service': service,
                        'environment': environment,
                        'source': 'operations-console',
                    },
                },
                stats=stats,
            )
            backdate(
                message,
                created_at=event_time + timedelta(minutes=20 + turn_index * 5),
            )

        for tool_index, tool_name in enumerate(TOOL_NAMES):
            failed = (session_index + tool_index) % 9 == 0
            invocation = get_or_create_json_key(
                AIOpsToolInvocation,
                json_field='request_payload',
                seed_key=f'aiops-tool-{session_index + 1:02d}-{tool_index + 1:02d}',
                defaults={
                    'session': session,
                    'message': assistant,
                    'tool_name': tool_name,
                    'status': 'failed' if failed else 'success',
                    'latency_ms': 140 + session_index * 35 + tool_index * 70,
                    'request_payload': {
                        'service': service,
                        'environment': environment,
                    },
                    'response_summary': {
                        'matched': 0 if failed else 6 + session_index,
                        'error': 'upstream timeout' if failed else '',
                    },
                },
                stats=stats,
            )
            backdate(
                invocation,
                created_at=event_time + timedelta(minutes=2 + tool_index * 2),
            )

        for purpose_index, purpose in enumerate(MODEL_PURPOSES):
            failed = (session_index + purpose_index) % 11 == 0
            prompt_tokens = 900 + session_index * 80
            completion_tokens = 260 + purpose_index * 60
            total_tokens = prompt_tokens + completion_tokens
            invocation = get_or_create_json_key(
                AIOpsModelInvocation,
                json_field='request_summary',
                seed_key=f'aiops-model-{session_index + 1:02d}-{purpose_index + 1:02d}',
                defaults={
                    'provider': provider,
                    'session': session,
                    'message': assistant,
                    'username': base['user'].username,
                    'purpose': purpose,
                    'requested_model': (
                        provider.default_model if provider else 'ops-reasoner-32b'
                    ),
                    'resolved_model': (
                        provider.default_model if provider else 'ops-reasoner-32b'
                    ),
                    'status': 'failed' if failed else 'success',
                    'latency_ms': 820 + session_index * 95 + purpose_index * 180,
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': total_tokens,
                    'estimated_cost_usd': (
                        Decimal(total_tokens) * Decimal('0.000002')
                    ).quantize(Decimal('0.000001')),
                    'estimated_cost_currency': 'USD',
                    'request_summary': {
                        'service': service,
                        'environment': environment,
                    },
                    'response_summary': {
                        'finish_reason': 'error' if failed else 'stop',
                        'error_type': (
                            'rate_limited' if session_index % 2 == 0 else 'timeout'
                        ) if failed else '',
                    },
                },
                stats=stats,
            )
            backdate(
                invocation,
                created_at=event_time + timedelta(minutes=10 + purpose_index * 2),
            )

        action_status = ACTION_STATUSES[session_index]
        action = get_or_create_json_key(
            AIOpsPendingAction,
            json_field='action_payload',
            seed_key=f'aiops-action-{session_index + 1:02d}',
            defaults={
                'session': session,
                'message': assistant,
                'action_type': 'execute_host_task',
                'title': f'{service} 诊断与恢复任务',
                'risk_level': ('low', 'medium', 'high', 'critical')[session_index % 4],
                'status': action_status,
                'action_payload': {
                    'operation': 'diagnose_service',
                    'service': service,
                    'environment': environment,
                },
                'result_payload': (
                    {'summary': '任务步骤已记录'} if action_status == 'executed'
                    else {'error_type': 'policy_blocked'} if action_status == 'failed'
                    else {}
                ),
                'confirmed_by': (
                    'SRE-王涛' if action_status in {'confirmed', 'executed'} else ''
                ),
                'confirmed_at': (
                    event_time + timedelta(minutes=22)
                    if action_status in {'confirmed', 'executed'} else None
                ),
            },
            stats=stats,
        )
        backdate(
            action,
            created_at=event_time + timedelta(minutes=21),
            updated_at=event_time + timedelta(minutes=22),
        )
        sessions.append(session)
    return sessions


def _seed_external_tasks(stats, base, now):
    tasks = []
    for index, (title, service, environment) in enumerate(TOPICS):
        public_id = uuid.uuid5(uuid.NAMESPACE_URL, f'ai-ops-production-task-{index}')
        status = TASK_STATUSES[index]
        task, created = AIOpsExternalTask.objects.get_or_create(
            public_id=public_id,
            defaults={
                'source_agent': 'incident-analysis-agent',
                'title': title,
                'action_code': 'incident_analysis',
                'agent_mode': 'orchestrated',
                'status': status,
                'input_payload': {'service': service, 'environment': environment},
                'plan_steps': ['收集告警', '检索日志与指标', '分析变更', '生成处置建议'],
                'orchestration_state': {
                    'current_step': 4 if status == 'completed' else 2
                },
                'agent_results': [{'agent': 'observability', 'status': 'success'}],
                'react_trace': [
                    {'thought': '关联最近变更与异常窗口', 'action': 'query_context'}
                ],
                'result_payload': {'summary': '分析完成'} if status == 'completed' else {},
                'error_message': '上下文查询超时' if status == 'failed' else '',
                'created_by': base['user'],
                'completed_at': (
                    now - timedelta(days=HISTORY_DAYS[index])
                    if status == 'completed' else None
                ),
                'canceled_at': (
                    now - timedelta(days=HISTORY_DAYS[index])
                    if status == 'canceled' else None
                ),
            },
        )
        stats.record(created)
        task._production_seed_created = created
        backdate(
            task,
            created_at=now - timedelta(days=HISTORY_DAYS[index]),
            updated_at=now - timedelta(days=HISTORY_DAYS[index]),
        )
        tasks.append(task)
    return tasks


def _seed_runbooks(stats, base, sessions, tasks, now):
    runbooks = []
    for index, (slug, title, service) in enumerate(RUNBOOK_SPECS):
        runbook, created = AIOpsRunbook.objects.get_or_create(
            slug=slug,
            defaults={
                'title': title,
                'environment': 'prod',
                'service': service,
                'status': 'published',
                'version': 1,
                'content': (
                    '1. 确认影响范围\n2. 保存现场证据\n3. 执行最小风险处置\n'
                    '4. 验证核心指标\n5. 持续观察并复盘'
                ),
                'evidence': [{'type': 'alert', 'id': base['alert'].pk}],
                'tags': ['incident', 'operations', service],
                'source_refs': [
                    {'type': 'session', 'id': sessions[index % len(sessions)].pk}
                ],
                'source_task': tasks[index % len(tasks)],
                'source_session': sessions[index % len(sessions)],
                'created_by': 'SRE-王涛',
                'updated_by': 'SRE-王涛',
                'published_at': now - timedelta(days=HISTORY_DAYS[index]),
                'archived_at': None,
            },
        )
        stats.record(created)
        if created:
            AIOpsRunbookVersion.objects.create(
                runbook=runbook,
                version=1,
                status='published',
                title=title,
                content=runbook.content,
                evidence=runbook.evidence,
                tags=runbook.tags,
                source_refs=runbook.source_refs,
                change_note='建立标准处置流程',
                created_by='SRE-王涛',
            )
            stats.record(True)
        runbooks.append(runbook)
    return runbooks


def _seed_reviews(stats, base, sessions, tasks, runbooks, now):
    for index, (title, service, environment) in enumerate(TOPICS):
        review, created = AIOpsReviewKnowledge.objects.get_or_create(
            slug=f'review-{index + 1:02d}',
            defaults={
                'title': f'{title}复盘',
                'summary': (
                    f'{service} 异常由容量波动与下游依赖延迟共同触发，'
                    '已完成处置并补充监控。'
                ),
                'environment': environment,
                'service': service,
                'source_type': 'session',
                'evidence': [{'type': 'alert', 'id': base['alert'].pk}],
                'tags': ['postmortem', service, environment],
                'source_refs': [
                    {'type': 'external_task', 'id': str(tasks[index].public_id)}
                ],
                'source_session': sessions[index],
                'source_task': tasks[index],
                'source_runbook': runbooks[index % len(runbooks)],
                'created_by': 'SRE-王涛',
                'updated_by': 'SRE-王涛',
            },
        )
        stats.record(created)
        review._production_seed_created = created
        backdate(
            review,
            created_at=now - timedelta(days=HISTORY_DAYS[index]),
            updated_at=now - timedelta(days=HISTORY_DAYS[index]),
        )


def seed_aiops(stats, base, task_context, alert_context, obs_context):
    del alert_context
    now = timezone.now()
    provider = _resolve_provider(stats)
    _seed_knowledge_environments(stats, base, task_context, obs_context, now)
    sessions = _seed_sessions_and_audit(stats, base, provider, now)
    tasks = _seed_external_tasks(stats, base, now)
    runbooks = _seed_runbooks(stats, base, sessions, tasks, now)
    _seed_reviews(stats, base, sessions, tasks, runbooks, now)
