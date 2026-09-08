from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone
from .models import CIType, ConfigItem, CIRelation, CostRecord, ResourceRequest, ResourceNode
from .serializers import (
    CITypeSerializer, ConfigItemSerializer, CIRelationSerializer,
    CostRecordSerializer, ResourceRequestSerializer, ResourceNodeSerializer
)
from ops.models import Host
from rbac.permissions import RBACPermissionMixin, build_rbac_permission
from rbac.services import user_has_permissions
from .sync import (
    is_placeholder_ci_type_name,
    normalize_ci_attributes,
    normalize_ci_type_name,
    resolve_config_item_type_meta,
)


SEVERITY_ORDER = {'danger': 3, 'warning': 2, 'info': 1}
TYPE_LABELS = {
    'reclaim': '资源回收',
    'schedule': '定时启停',
    'downsize': '规格缩容',
    'storage': '存储分层',
    'governance': '归属治理',
}
SEVERITY_LABELS = {
    'danger': '高优先',
    'warning': '中优先',
    'info': '治理项',
}


def _current_month():
    return timezone.now().strftime('%Y-%m')


def _normalize_month(value):
    month = (value or '').strip()
    if not month:
        return _current_month()
    if not re.fullmatch(r'\d{4}-\d{2}', month):
        return _current_month()
    try:
        datetime.strptime(f'{month}-01', '%Y-%m-%d')
    except ValueError:
        return _current_month()
    return month


def _previous_months(limit=6, month=None):
    base = datetime.strptime(f"{_normalize_month(month)}-01", '%Y-%m-%d')
    months = []
    for _ in range(limit):
        months.append(base.strftime('%Y-%m'))
        base = (base.replace(day=1) - timezone.timedelta(days=1)).replace(day=1)
    months.reverse()
    return months


def _to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _to_float(value):
    return float(value or 0)


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'y', 'on'}
    return bool(value)


def _safe_percent(part, whole):
    if not whole:
        return 0.0
    return round(_to_float((part / whole) * Decimal('100')), 1)


def _normalize_business_line(value):
    return value or '未归类'


def _normalize_provider(value):
    return value or '未标记'


def _provider_for_attributes(attributes):
    return (
        (attributes or {}).get('billing_provider')
        or (attributes or {}).get('cloud_provider')
        or (attributes or {}).get('provider')
        or ''
    )[:50]


def _cost_rows_for_month(month):
    if month == _current_month():
        existing_rows = list(
            CostRecord.objects.filter(month=month)
            .select_related('ci__ci_type')
            .order_by('-computed_at', '-id')
        )
        row_map = {}
        for row in existing_rows:
            if row.ci_id not in row_map:
                row_map[row.ci_id] = {
                    'ci': row.ci,
                    'amount': row.amount or Decimal('0'),
                    'provider': row.provider or _provider_for_attributes(row.ci.attributes or {}),
                }
            else:
                row_map[row.ci_id]['amount'] += row.amount or Decimal('0')
                if not row_map[row.ci_id]['provider'] and row.provider:
                    row_map[row.ci_id]['provider'] = row.provider

        for ci in ConfigItem.objects.select_related('ci_type').all():
            if ci.id in row_map:
                continue
            amount = _to_decimal((ci.attributes or {}).get('monthly_cost')) or Decimal('0')
            if amount <= 0:
                continue
            row_map[ci.id] = {
                'ci': ci,
                'amount': amount,
                'provider': _provider_for_attributes(ci.attributes or {}),
            }

        return list(row_map.values())

    return [
        {
            'ci': record.ci,
            'amount': record.amount or Decimal('0'),
            'provider': record.provider or _provider_for_attributes(record.ci.attributes or {}),
        }
        for record in CostRecord.objects.filter(month=month)
        .select_related('ci__ci_type')
        .order_by('-amount', 'ci__name')
    ]


def _month_cost_map(month):
    return {
        row['ci'].id: row['amount']
        for row in _cost_rows_for_month(month)
    }


def _cost_amount_for_ci(ci, month_costs):
    amount = month_costs.get(ci.id)
    if amount is not None:
        return amount
    return Decimal('0')


def _add_candidate(candidates, *, candidate_type, severity, ratio, monthly_cost, title, detail, action, evidence):
    if ratio <= 0:
        return
    potential_saving = (monthly_cost * ratio).quantize(Decimal('0.01'))
    optimized_cost = max(monthly_cost - potential_saving, Decimal('0'))
    candidates.append({
        'type': candidate_type,
        'type_label': TYPE_LABELS[candidate_type],
        'severity': severity,
        'severity_label': SEVERITY_LABELS[severity],
        'title': title,
        'detail': detail,
        'action': action,
        'evidence': evidence,
        'potential_saving': potential_saving,
        'optimized_monthly_cost': optimized_cost,
        'saving_rate': round(_to_float(ratio * Decimal('100')), 1),
    })


def _best_suggestion_for_ci(ci, monthly_cost):
    attributes = ci.attributes or {}
    cpu = _to_decimal(attributes.get('cpu')) or Decimal('0')
    memory_gb = _to_decimal(attributes.get('memory_gb')) or Decimal('0')
    avg_cpu_usage = _to_decimal(attributes.get('avg_cpu_usage'))
    avg_memory_usage = _to_decimal(attributes.get('avg_memory_usage'))
    storage_gb = _to_decimal(attributes.get('storage_gb') or attributes.get('disk_gb')) or Decimal('0')
    storage_utilization = _to_decimal(attributes.get('storage_utilization') or attributes.get('storage_usage_pct') or attributes.get('disk_usage_pct'))
    always_on = _to_bool(attributes.get('always_on'))
    schedule_exempt = _to_bool(attributes.get('schedule_exempt'))
    offline_days = int(_to_decimal(attributes.get('offline_days')) or 0)
    candidates = []

    if ci.status in {'offline', 'decommissioned'}:
        _add_candidate(
            candidates,
            candidate_type='reclaim',
            severity='danger',
            ratio=Decimal('1.00'),
            monthly_cost=monthly_cost,
            title=f'回收下线资源：{ci.name}',
            detail='资源已经离线或下线，但仍在持续计费，适合优先释放实例、磁盘和公网能力。',
            action='确认业务已迁移后直接回收实例及其挂载资源，避免继续产生整月账单。',
            evidence=f'当前状态为 {ci.status}，已离线 {offline_days or 0} 天。',
        )

    if ci.status == 'idle' or (ci.environment in {'dev', 'test'} and monthly_cost >= Decimal('200') and (avg_cpu_usage or Decimal('0')) <= Decimal('10')):
        ratio = Decimal('0.70') if ci.status == 'idle' else Decimal('0.60')
        _add_candidate(
            candidates,
            candidate_type='reclaim',
            severity='warning',
            ratio=ratio,
            monthly_cost=monthly_cost,
            title=f'回收空闲资源：{ci.name}',
            detail='资源长时间处于空闲状态，继续保留完整规格会持续吞噬预算。',
            action='如仍需保留镜像或数据，先做快照后释放主机；否则直接回收。',
            evidence=f'环境 {ci.environment}，平均 CPU {(avg_cpu_usage or Decimal("0"))}% 。',
        )

    if ci.environment in {'dev', 'test'} and monthly_cost >= Decimal('300') and not schedule_exempt and (always_on or (avg_cpu_usage or Decimal('0')) <= Decimal('25')):
        ratio = Decimal('0.55') if always_on else Decimal('0.40')
        severity = 'danger' if monthly_cost >= Decimal('800') else 'warning'
        _add_candidate(
            candidates,
            candidate_type='schedule',
            severity=severity,
            ratio=ratio,
            monthly_cost=monthly_cost,
            title=f'为非生产资源启用定时启停：{ci.name}',
            detail='测试与开发资源夜间和周末通常负载很低，适合通过自动关停快速降本。',
            action='建议设置工作日 08:00-20:00 运行窗口，夜间与周末自动关机。',
            evidence=f'环境 {ci.environment}，平均 CPU {(avg_cpu_usage or Decimal("0"))}% ，当前保持 24x7 运行。',
        )

    if monthly_cost >= Decimal('1000') and (cpu >= Decimal('8') or memory_gb >= Decimal('16')) and (avg_cpu_usage is None or avg_cpu_usage <= Decimal('35')) and (avg_memory_usage is None or avg_memory_usage <= Decimal('55')):
        ratio = Decimal('0.25') if ci.environment == 'prod' else Decimal('0.35')
        severity = 'danger' if monthly_cost >= Decimal('1800') else 'warning'
        _add_candidate(
            candidates,
            candidate_type='downsize',
            severity=severity,
            ratio=ratio,
            monthly_cost=monthly_cost,
            title=f'缩容高成本资源：{ci.name}',
            detail='实例规格明显高于日常负载，适合降配或切换到更低成本的实例族。',
            action='根据近两周峰值使用率回收 25%~35% 资源规格，并保留弹性扩容余量。',
            evidence=f'当前规格 {cpu}C/{memory_gb}G，平均 CPU {(avg_cpu_usage or Decimal("0"))}% ，平均内存 {(avg_memory_usage or Decimal("0"))}% 。',
        )

    if storage_gb >= Decimal('500') and monthly_cost >= Decimal('400') and storage_utilization is not None and storage_utilization <= Decimal('55'):
        ratio = Decimal('0.25') if storage_utilization <= Decimal('35') else Decimal('0.18')
        _add_candidate(
            candidates,
            candidate_type='storage',
            severity='warning',
            ratio=ratio,
            monthly_cost=monthly_cost,
            title=f'优化存储分层：{ci.name}',
            detail='数据量大但利用率偏低，适合冷热分层、压缩或归档到低频存储。',
            action='将低频访问数据迁移到低频或归档层，只保留最近 30 天热数据。',
            evidence=f'存储容量 {storage_gb}GB，当前利用率 {storage_utilization}% 。',
        )

    if (not ci.business_line or not ci.admin_user) and monthly_cost >= Decimal('200'):
        _add_candidate(
            candidates,
            candidate_type='governance',
            severity='info',
            ratio=Decimal('0.08'),
            monthly_cost=monthly_cost,
            title=f'补齐归属治理信息：{ci.name}',
            detail='缺少业务线或负责人会导致账单归集困难，也不利于后续回收和预算控制。',
            action='补齐标签、负责人和预算归属后，再纳入月度成本 review 清单。',
            evidence='当前存在缺失的业务归属或负责人字段。',
        )

    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            item['potential_saving'],
            SEVERITY_ORDER.get(item['severity'], 0),
        ),
    )


def _serialize_suggestion(item):
    payload = dict(item)
    payload['monthly_cost'] = _to_float(item['monthly_cost'])
    payload['potential_saving'] = _to_float(item['potential_saving'])
    payload['optimized_monthly_cost'] = _to_float(item['optimized_monthly_cost'])
    return payload


def _build_optimization(month):
    month_costs = _month_cost_map(month)

    suggestions = []
    total_monthly_cost = Decimal('0')
    for ci in ConfigItem.objects.select_related('ci_type').all():
        monthly_cost = _cost_amount_for_ci(ci, month_costs)
        if monthly_cost <= 0:
            continue
        total_monthly_cost += monthly_cost
        suggestion = _best_suggestion_for_ci(ci, monthly_cost)
        if not suggestion:
            continue
        suggestions.append({
            'ci_id': ci.id,
            'ci_name': ci.name,
            'ci_type': ci.ci_type.name,
            'environment': ci.environment,
            'business_line': _normalize_business_line(ci.business_line),
            'admin_user': ci.admin_user or '待认领',
            'monthly_cost': monthly_cost,
            **suggestion,
        })

    suggestions.sort(
        key=lambda item: (
            item['potential_saving'],
            SEVERITY_ORDER.get(item['severity'], 0),
            item['monthly_cost'],
        ),
        reverse=True,
    )

    total_potential_saving = sum((item['potential_saving'] for item in suggestions), Decimal('0'))
    optimized_monthly_cost = max(total_monthly_cost - total_potential_saving, Decimal('0'))
    annualized_saving = total_potential_saving * Decimal('12')

    by_type_map = defaultdict(lambda: {'count': 0, 'total_saving': Decimal('0')})
    by_severity_map = defaultdict(lambda: {'count': 0, 'total_saving': Decimal('0')})
    by_business_map = defaultdict(lambda: {'count': 0, 'total_saving': Decimal('0')})
    for item in suggestions:
        by_type_map[item['type']]['count'] += 1
        by_type_map[item['type']]['total_saving'] += item['potential_saving']

        by_severity_map[item['severity']]['count'] += 1
        by_severity_map[item['severity']]['total_saving'] += item['potential_saving']

        by_business_map[item['business_line']]['count'] += 1
        by_business_map[item['business_line']]['total_saving'] += item['potential_saving']

    by_type = [
        {
            'type': key,
            'label': TYPE_LABELS.get(key, key),
            'count': value['count'],
            'total_saving': _to_float(value['total_saving']),
        }
        for key, value in by_type_map.items()
    ]
    by_type.sort(key=lambda item: item['total_saving'], reverse=True)

    by_severity = [
        {
            'severity': key,
            'label': SEVERITY_LABELS.get(key, key),
            'count': value['count'],
            'total_saving': _to_float(value['total_saving']),
        }
        for key, value in by_severity_map.items()
    ]
    by_severity.sort(key=lambda item: SEVERITY_ORDER.get(item['severity'], 0), reverse=True)

    by_business = [
        {
            'business_line': key,
            'count': value['count'],
            'total_saving': _to_float(value['total_saving']),
        }
        for key, value in by_business_map.items()
    ]
    by_business.sort(key=lambda item: item['total_saving'], reverse=True)

    serialized_suggestions = [_serialize_suggestion(item) for item in suggestions[:12]]
    quick_wins = serialized_suggestions[:5]

    return {
        'month': month,
        'total_monthly_cost': _to_float(total_monthly_cost),
        'suggestions': serialized_suggestions,
        'quick_wins': quick_wins,
        'total_potential_saving': _to_float(total_potential_saving),
        'optimized_monthly_cost': _to_float(optimized_monthly_cost),
        'annualized_saving': _to_float(annualized_saving),
        'saving_rate': _safe_percent(total_potential_saving, total_monthly_cost),
        'suggestion_count': len(suggestions),
        'affected_resource_count': len(suggestions),
        'by_type': by_type,
        'by_severity': by_severity,
        'by_business': by_business,
    }


def _build_cost_report(month):
    rows = _cost_rows_for_month(month)
    total = sum((row['amount'] for row in rows), Decimal('0'))

    by_business_map = defaultdict(lambda: {'total_cost': Decimal('0'), 'ci_ids': set()})
    by_environment_map = defaultdict(lambda: {'total_cost': Decimal('0'), 'ci_ids': set()})
    by_type_map = defaultdict(lambda: {'total_cost': Decimal('0'), 'ci_ids': set()})
    by_provider_map = defaultdict(lambda: {'total_cost': Decimal('0'), 'ci_ids': set()})

    for row in rows:
        ci = row['ci']
        amount = row['amount']
        business_line = _normalize_business_line(ci.business_line)
        environment = ci.environment
        type_name = ci.ci_type.name
        provider = _normalize_provider(row['provider'])

        by_business_map[business_line]['total_cost'] += amount
        by_business_map[business_line]['ci_ids'].add(ci.id)

        by_environment_map[environment]['total_cost'] += amount
        by_environment_map[environment]['ci_ids'].add(ci.id)

        by_type_map[type_name]['total_cost'] += amount
        by_type_map[type_name]['ci_ids'].add(ci.id)

        by_provider_map[provider]['total_cost'] += amount
        by_provider_map[provider]['ci_ids'].add(ci.id)

    by_business = [
        {
            'business_line': key,
            'total_cost': _to_float(value['total_cost']),
            'count': len(value['ci_ids']),
        }
        for key, value in by_business_map.items()
    ]
    by_business.sort(key=lambda item: (-item['total_cost'], item['business_line']))

    by_environment = [
        {
            'environment': key,
            'total_cost': _to_float(value['total_cost']),
            'count': len(value['ci_ids']),
        }
        for key, value in by_environment_map.items()
    ]
    by_environment.sort(key=lambda item: (-item['total_cost'], item['environment']))

    by_type = [
        {
            'type_name': key,
            'total_cost': _to_float(value['total_cost']),
            'count': len(value['ci_ids']),
        }
        for key, value in by_type_map.items()
    ]
    by_type.sort(key=lambda item: (-item['total_cost'], item['type_name']))

    by_provider = [
        {
            'provider': key,
            'total_cost': _to_float(value['total_cost']),
            'count': len(value['ci_ids']),
        }
        for key, value in by_provider_map.items()
    ]
    by_provider.sort(key=lambda item: (-item['total_cost'], item['provider']))

    top_cost_items = [
        {
            'ci_id': row['ci'].id,
            'name': row['ci'].name,
            'business_line': _normalize_business_line(row['ci'].business_line),
            'environment': row['ci'].environment,
            'type_name': row['ci'].ci_type.name,
            'monthly_cost': _to_float(row['amount']),
            'provider': _normalize_provider(row['provider']),
        }
        for row in sorted(rows, key=lambda item: (-item['amount'], item['ci'].name))[:10]
    ]

    optimization = _build_optimization(month)
    cost_trend = []
    for period in _previous_months(6, month):
        period_total = sum((row['amount'] for row in _cost_rows_for_month(period)), Decimal('0'))
        item = {'period': period, 'total': _to_float(period_total)}
        if period == month:
            item['projected_total'] = max(item['total'] - optimization['total_potential_saving'], 0)
            item['projected_saving'] = optimization['total_potential_saving']
        cost_trend.append(item)

    non_prod_cost_total = sum(
        (Decimal(str(item['total_cost'])) for item in by_environment if item['environment'] in {'dev', 'test'}),
        Decimal('0'),
    )
    avg_cost_per_resource = (total / len(rows)) if rows else Decimal('0')
    top_business = by_business[0] if by_business else {'business_line': '-', 'total_cost': 0}
    top_provider = by_provider[0] if by_provider else {'provider': '-', 'total_cost': 0}

    return {
        'month': month,
        'total_monthly_cost': _to_float(total),
        'optimized_monthly_cost': optimization['optimized_monthly_cost'],
        'total_potential_saving': optimization['total_potential_saving'],
        'annualized_saving': optimization['annualized_saving'],
        'saving_rate': optimization['saving_rate'],
        'by_business': by_business,
        'by_environment': by_environment,
        'by_type': by_type,
        'by_provider': by_provider,
        'top_cost_items': top_cost_items,
        'cost_trend': cost_trend,
        'non_prod_cost_total': _to_float(non_prod_cost_total),
        'non_prod_cost_ratio': _safe_percent(non_prod_cost_total, total),
        'avg_cost_per_resource': _to_float(avg_cost_per_resource),
        'top_business_line': top_business['business_line'],
        'top_business_cost': top_business['total_cost'],
        'top_provider': top_provider['provider'],
        'top_provider_cost': top_provider['total_cost'],
        'optimization_preview': {
            'suggestion_count': optimization['suggestion_count'],
            'affected_resource_count': optimization['affected_resource_count'],
            'total_potential_saving': optimization['total_potential_saving'],
            'optimized_monthly_cost': optimization['optimized_monthly_cost'],
            'annualized_saving': optimization['annualized_saving'],
            'saving_rate': optimization['saving_rate'],
        },
        'recommendations_preview': optimization['quick_wins'],
    }


class CITypeViewSet(RBACPermissionMixin, viewsets.ModelViewSet):
    """CI 类型管理"""
    queryset = CIType.objects.annotate(ci_count=Count('instances'))
    serializer_class = CITypeSerializer
    search_fields = ['name']
    pagination_class = None
    rbac_permissions = {
        'list': ['cmdb.ci.view'],
        'retrieve': ['cmdb.ci.view'],
        'create': ['cmdb.ci.manage'],
        'update': ['cmdb.ci.manage'],
        'partial_update': ['cmdb.ci.manage'],
        'destroy': ['cmdb.ci.manage'],
    }

    def list(self, request, *args, **kwargs):
        search = (request.query_params.get('search') or '').strip().lower()
        grouped = {}
        for ci_type in self.get_queryset():
            canonical_name = normalize_ci_type_name(ci_type.name)
            if is_placeholder_ci_type_name(canonical_name):
                continue
            row = grouped.get(canonical_name)
            if row is None:
                row = {
                    'id': ci_type.id,
                    'name': canonical_name,
                    'icon': ci_type.icon,
                    'color': ci_type.color,
                    'description': ci_type.description,
                    'created_at': ci_type.created_at,
                    'ci_count': 0,
                }
                grouped[canonical_name] = row
            if canonical_name == ci_type.name:
                row['id'] = ci_type.id
                row['icon'] = ci_type.icon or row['icon']
                row['color'] = ci_type.color or row['color']
                row['description'] = ci_type.description or row['description']
                row['created_at'] = ci_type.created_at
            row['ci_count'] += getattr(ci_type, 'ci_count', 0)

        rows = list(grouped.values())
        if search:
            rows = [row for row in rows if search in (row['name'] or '').lower()]
        rows.sort(key=lambda item: (-item['ci_count'], item['name']))
        return Response(rows)

class ConfigItemViewSet(RBACPermissionMixin, viewsets.ModelViewSet):
    """配置项管理"""
    queryset = ConfigItem.objects.select_related('ci_type').all().order_by('-updated_at', '-id')
    serializer_class = ConfigItemSerializer
    search_fields = [
        'name',
        'admin_user',
        'business_line',
        'ci_type__name',
        'attributes__ip_address',
        'attributes__ip',
        'attributes__private_ip',
        'attributes__public_ip',
        'attributes__host_ip',
        'attributes__docker_environment_ip',
        'attributes__description',
        'attributes__specification',
        'attributes__instance_type',
    ]
    filterset_fields = ['ci_type', 'business_line', 'environment', 'status']
    rbac_permissions = {
        'list': ['cmdb.ci.view'],
        'retrieve': ['cmdb.ci.view'],
        'create': ['cmdb.ci.manage'],
        'update': ['cmdb.ci.manage'],
        'partial_update': ['cmdb.ci.manage'],
        'destroy': ['cmdb.ci.manage'],
        'stats': ['cmdb.ci.view'],
    }

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = self.filter_queryset(self.get_queryset())
        by_type_map = {}
        for item in qs:
            type_meta = resolve_config_item_type_meta(item)
            normalized_name = normalize_ci_type_name(type_meta['name'])
            bucket = by_type_map.setdefault(
                normalized_name,
                {
                    'ci_type': item.ci_type_id,
                    'ci_type__name': normalized_name,
                    'ci_type__color': type_meta['color'] or '#9c27b0',
                    'count': 0,
                },
            )
            bucket['count'] += 1
        by_type = sorted(by_type_map.values(), key=lambda entry: entry['count'], reverse=True)
        by_status = dict(qs.values_list('status').annotate(count=Count('id')))
        by_env = dict(qs.values_list('environment').annotate(count=Count('id')))
        return Response({
            'total': qs.count(),
            'by_type': by_type,
            'by_status': by_status,
            'by_env': by_env,
        })

    def perform_create(self, serializer):
        serializer.save(attributes=normalize_ci_attributes(serializer.validated_data.get('attributes')))

    def perform_update(self, serializer):
        attributes = serializer.validated_data.get('attributes', serializer.instance.attributes if serializer.instance else {})
        serializer.save(attributes=normalize_ci_attributes(attributes))

class ResourceNodeViewSet(RBACPermissionMixin, viewsets.ModelViewSet):
    """资源节点(业务线/环境)树管理"""
    queryset = ResourceNode.objects.all().order_by('sort_order', 'id')
    serializer_class = ResourceNodeSerializer
    filterset_fields = ['node_type', 'parent']
    pagination_class = None
    rbac_permissions = {
        'list': ['cmdb.ci.view'],
        'retrieve': ['cmdb.ci.view'],
        'create': ['cmdb.ci.manage'],
        'update': ['cmdb.ci.manage'],
        'partial_update': ['cmdb.ci.manage'],
        'destroy': ['cmdb.ci.manage'],
        'tree': ['cmdb.ci.view'],
    }

    @action(detail=False, methods=['get'])
    def tree(self, request):
        nodes = list(ResourceNode.objects.all().order_by('sort_order', 'id').values())
        return Response(self._build_tree(nodes, None))

    def _build_tree(self, nodes, parent_id):
        tree = []
        for node in nodes:
            if node['parent_id'] == parent_id:
                children = self._build_tree(nodes, node['id'])
                if children:
                    node['children'] = children
                tree.append(node)
        return tree

class CIRelationViewSet(RBACPermissionMixin, viewsets.ModelViewSet):
    """CI 关系管理"""
    queryset = CIRelation.objects.select_related('source', 'target').all()
    serializer_class = CIRelationSerializer
    filterset_fields = ['source', 'target', 'relation_type']
    rbac_permissions = {
        'list': ['cmdb.ci.view'],
        'retrieve': ['cmdb.ci.view'],
        'create': ['cmdb.ci.manage'],
        'update': ['cmdb.ci.manage'],
        'partial_update': ['cmdb.ci.manage'],
        'destroy': ['cmdb.ci.manage'],
    }

class CostRecordViewSet(RBACPermissionMixin, viewsets.ModelViewSet):
    """成本记录管理"""
    queryset = CostRecord.objects.select_related('ci').all()
    serializer_class = CostRecordSerializer
    filterset_fields = ['ci', 'month']
    rbac_permissions = {
        'list': ['cmdb.cost.view'],
        'retrieve': ['cmdb.cost.view'],
        'create': ['cmdb.ci.manage'],
        'update': ['cmdb.ci.manage'],
        'partial_update': ['cmdb.ci.manage'],
        'destroy': ['cmdb.ci.manage'],
    }

class ResourceRequestViewSet(RBACPermissionMixin, viewsets.ModelViewSet):
    """资源申请管理"""
    queryset = ResourceRequest.objects.all().order_by('-created_at', '-id')
    serializer_class = ResourceRequestSerializer
    search_fields = ['title', 'applicant', 'resource_type', 'business_line', 'specification', 'reason']
    filterset_fields = ['status', 'resource_type', 'business_line', 'environment', 'priority']
    rbac_permissions = {
        'list': [],
        'retrieve': [],
        'create': ['cmdb.request.submit'],
        'update': ['cmdb.request.approve'],
        'partial_update': ['cmdb.request.approve'],
        'destroy': ['cmdb.request.approve'],
        'approve': ['cmdb.request.approve'],
        'reject': ['cmdb.request.approve'],
        'complete': ['cmdb.request.approve'],
    }

    def _can_view_requests(self, user):
        return (
            user_has_permissions(user, ['cmdb.ci.view'])
            or user_has_permissions(user, ['cmdb.request.submit'])
            or user_has_permissions(user, ['cmdb.request.approve'])
        )

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated:
            return qs.none()
        if user_has_permissions(user, ['cmdb.ci.view']) or user_has_permissions(user, ['cmdb.request.approve']):
            return qs
        if user_has_permissions(user, ['cmdb.request.submit']):
            return qs.filter(applicant=user.username)
        return qs.none()

    def list(self, request, *args, **kwargs):
        if not self._can_view_requests(request.user):
            return Response({'detail': '缺少资源申请查看权限'}, status=403)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not self._can_view_requests(request.user):
            return Response({'detail': '缺少资源申请查看权限'}, status=403)
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(applicant=self.request.user.username)

    def _build_host_sync_payload(self, obj, fulfillment_note=''):
        specs = obj.specs or {}
        hostname = (specs.get('hostname') or '').strip()
        ip_address = (specs.get('ip_address') or '').strip()
        if obj.quantity and obj.quantity > 1:
            raise ValueError('当前一次仅支持将单台主机申请转为主机资产，请拆分申请后再交付')
        if not hostname or not ip_address:
            raise ValueError('完成交付前请先在主机申请中填写主机名和 IP 地址')

        description_parts = [obj.title, obj.reason, fulfillment_note]
        description = '；'.join([part.strip() for part in description_parts if part and part.strip()])[:200]
        return {
            'hostname': hostname,
            'ip_address': ip_address,
            'business_line': (obj.business_line or '').strip(),
            'environment': (obj.environment or '').strip(),
            'admin_user': (specs.get('admin_user') or obj.applicant or '').strip(),
            'os_type': (specs.get('os_type') or 'Linux').strip() or 'Linux',
            'instance_type': (specs.get('instance_type') or '').strip(),
            'specification': (obj.specification or specs.get('specification') or '').strip(),
            'description': description,
        }

    def _sync_request_to_host_assets(self, obj, fulfillment_note=''):
        payload = self._build_host_sync_payload(obj, fulfillment_note=fulfillment_note)
        host, _ = Host.objects.update_or_create(
            hostname=payload['hostname'],
            defaults={
                'ip_address': payload['ip_address'],
                'business_line': payload['business_line'],
                'environment': payload['environment'],
                'admin_user': payload['admin_user'],
                'os_type': payload['os_type'],
                'description': payload['description'],
                'status': 'online',
            },
        )

        ci_type, _ = CIType.objects.get_or_create(
            name='云主机(ECS)',
            defaults={
                'icon': 'Monitor',
                'color': '#64748b',
                'description': '承载应用与数据服务的云主机',
            },
        )
        config_item = ConfigItem.objects.filter(name=payload['hostname']).first()
        attributes = dict((config_item.attributes or {}) if config_item else {})
        attributes.update({
            'ip_address': payload['ip_address'],
            'os_type': payload['os_type'],
            'instance_type': payload['instance_type'],
            'specification': payload['specification'],
            'description': payload['description'],
            'source': 'host_request',
            'request_id': obj.id,
            'request_title': obj.title,
        })
        attributes = {
            key: value for key, value in attributes.items()
            if value not in (None, '')
        }

        if config_item is None:
            config_item = ConfigItem.objects.create(
                name=payload['hostname'],
                ci_type=ci_type,
                business_line=payload['business_line'],
                environment=payload['environment'] or 'prod',
                admin_user=payload['admin_user'],
                status='active',
                attributes=attributes,
            )
        else:
            config_item.ci_type = ci_type
            config_item.business_line = payload['business_line']
            config_item.environment = payload['environment'] or config_item.environment or 'prod'
            config_item.admin_user = payload['admin_user']
            config_item.status = 'active'
            config_item.attributes = attributes
            config_item.save()

        return host, config_item

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        obj = self.get_object()
        if obj.status != 'pending':
            return Response({'detail': '只能审批待审批资源'}, status=400)
        obj.status = 'approved'
        obj.approver = request.user.username
        obj.approval_comment = (request.data.get('comment') or request.data.get('approval_comment') or '').strip()
        obj.approved_at = timezone.now()
        obj.save(update_fields=['status', 'approver', 'approval_comment', 'approved_at', 'updated_at'])
        return Response(ResourceRequestSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        obj = self.get_object()
        if obj.status != 'pending':
            return Response({'detail': '只能审批待审批资源'}, status=400)
        obj.status = 'rejected'
        obj.approver = request.user.username
        obj.approval_comment = (request.data.get('comment') or request.data.get('approval_comment') or '').strip()
        obj.save(update_fields=['status', 'approver', 'approval_comment', 'updated_at'])
        return Response(ResourceRequestSerializer(obj).data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        obj = self.get_object()
        if obj.status != 'approved':
            return Response({'detail': '只能完成已批准资源'}, status=400)
        fulfillment_note = (request.data.get('note') or request.data.get('fulfillment_note') or '').strip()
        try:
            with transaction.atomic():
                self._sync_request_to_host_assets(obj, fulfillment_note=fulfillment_note)
                obj.status = 'completed'
                obj.fulfillment_note = fulfillment_note
                obj.completed_at = timezone.now()
                obj.save(update_fields=['status', 'fulfillment_note', 'completed_at', 'updated_at'])
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(ResourceRequestSerializer(obj).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated, build_rbac_permission('cmdb.dashboard.view')])
def cmdb_dashboard(request):
    month = _current_month()
    ci_total = ConfigItem.objects.count()
    ci_active = ConfigItem.objects.filter(status='active').count()
    ci_by_type = list(ConfigItem.objects.values(type_name=F('ci_type__name'), color=F('ci_type__color')).annotate(count=Count('id')).order_by('-count'))
    for item in ci_by_type:
        item['color'] = item.get('color') or '#9c27b0'
    ci_by_env = list(ConfigItem.objects.values('environment').annotate(count=Count('id')).order_by('-count'))
    cost_rows = _cost_rows_for_month(month)
    business_totals = defaultdict(lambda: {'count': 0, 'total_cost': Decimal('0')})
    for row in cost_rows:
        ci = row['ci']
        if not ci.business_line:
            continue
        business_totals[ci.business_line]['total_cost'] += row['amount']
    for business_line, count in (
        ConfigItem.objects.exclude(business_line='').values_list('business_line').annotate(count=Count('id'))
    ):
        business_totals[business_line]['count'] = count
    ci_by_biz = [
        {
            'business_line': business_line,
            'count': value['count'],
            'total_cost': _to_float(value['total_cost']),
        }
        for business_line, value in business_totals.items()
    ]
    ci_by_biz.sort(key=lambda item: (-item['total_cost'], item['business_line']))
    for item in ci_by_biz:
        item['total_cost'] = _to_float(item['total_cost'])
    total_monthly_cost = sum((row['amount'] for row in cost_rows), Decimal('0'))
    relation_count = CIRelation.objects.count()
    pending_requests = ResourceRequest.objects.filter(status='pending').count()

    return Response({
        'ci_total': ci_total,
        'ci_active': ci_active,
        'ci_by_type': ci_by_type,
        'ci_by_env': ci_by_env,
        'ci_by_business': ci_by_biz,
        'total_monthly_cost': _to_float(total_monthly_cost),
        'relation_count': relation_count,
        'pending_requests': pending_requests,
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated, build_rbac_permission('cmdb.topology.view')])
def cmdb_topology(request):
    ci_type_id = request.query_params.get('ci_type')
    business_line = request.query_params.get('business_line')
    environment = request.query_params.get('environment')
    scope = request.query_params.get('scope', 'neighbors')
    include_neighbors = scope != 'exact'

    filtered_qs = ConfigItem.objects.select_related('ci_type').all()
    if ci_type_id:
        filtered_qs = filtered_qs.filter(ci_type_id=ci_type_id)
    if business_line:
        filtered_qs = filtered_qs.filter(business_line=business_line)
    if environment:
        filtered_qs = filtered_qs.filter(environment=environment)

    matched_ids = set(filtered_qs.values_list('id', flat=True))
    node_ids = set(matched_ids)
    relations = CIRelation.objects.none()
    if matched_ids:
        relations = CIRelation.objects.filter(
            Q(source_id__in=matched_ids) | Q(target_id__in=matched_ids)
        ).select_related('source', 'target')
        if include_neighbors:
            for relation in relations:
                node_ids.add(relation.source_id)
                node_ids.add(relation.target_id)

    node_qs = ConfigItem.objects.select_related('ci_type').filter(id__in=node_ids).order_by(
        'business_line',
        'environment',
        'ci_type__name',
        'name',
    )
    nodes = []
    for ci in node_qs:
        attributes = ci.attributes or {}
        nodes.append({
            'id': ci.id,
            'name': ci.name,
            'type': ci.ci_type.name,
            'icon': ci.ci_type.icon,
            'color': ci.ci_type.color or '#9c27b0',
            'status': ci.status,
            'ip': attributes.get('ip_address') or attributes.get('ip', ''),
            'env': ci.environment,
            'business_line': ci.business_line,
            'admin_user': ci.admin_user,
            'monthly_cost': _to_float(attributes.get('monthly_cost')),
            'instance_type': attributes.get('instance_type', ''),
            'cloud_provider': attributes.get('cloud_provider', ''),
            'region': attributes.get('region', ''),
            'cpu': attributes.get('cpu'),
            'memory_gb': attributes.get('memory_gb'),
            'disk_gb': attributes.get('disk_gb'),
            'description': attributes.get('description', ''),
            'is_match': ci.id in matched_ids,
        })

    filtered_edges = []
    if node_ids:
        if not matched_ids:
            relations = CIRelation.objects.none()
        elif not include_neighbors:
            relations = CIRelation.objects.filter(
                source_id__in=node_ids,
                target_id__in=node_ids,
            ).select_related('source', 'target')
        for relation in relations:
            if relation.source_id in node_ids and relation.target_id in node_ids:
                filtered_edges.append({
                    'id': relation.id,
                    'source': relation.source_id,
                    'target': relation.target_id,
                    'source_name': relation.source.name,
                    'target_name': relation.target.name,
                    'type': relation.relation_type,
                    'label': relation.get_relation_type_display(),
                    'description': relation.description,
                    'is_match': relation.source_id in matched_ids and relation.target_id in matched_ids,
                })

    return Response({
        'nodes': nodes,
        'edges': filtered_edges,
        'meta': {
            'scope': 'neighbors' if include_neighbors else 'exact',
            'matched_node_ids': sorted(matched_ids),
            'node_count': len(nodes),
            'edge_count': len(filtered_edges),
        },
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated, build_rbac_permission('cmdb.cost.view')])
def cmdb_cost_report(request):
    month = _normalize_month(request.query_params.get('month'))
    return Response(_build_cost_report(month))

@api_view(['GET'])
@permission_classes([IsAuthenticated, build_rbac_permission('cmdb.cost.view')])
def cmdb_optimization(request):
    month = _normalize_month(request.query_params.get('month'))
    return Response(_build_optimization(month))
