from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from cmdb.demo_seed import BIZ_DATA, BIZ_INFRA
from ops.models import DeploymentApprovalFlow, DeploymentApprovalNode, TransactionTicket


DEMO_FLOW_PREFIX = '事务工单 · '
DEMO_OPERATOR = 'ops-demo'
SYSTEM_TRADE = '交易系统'


class Command(BaseCommand):
    help = '生成事务工单演示数据'

    def handle(self, *args, **options):
        self.stdout.write('正在生成事务工单演示数据...')
        now = timezone.now()

        flow_prod_change = self.upsert_flow(
            name='事务工单 · 生产变更审批',
            environment='prod',
            description='面向生产变更执行，覆盖研发、业务与运维三段确认。',
            nodes=[
                {'name': '研发负责人确认', 'order': 1, 'approver_type': 'user', 'approver_value': 'zhangsan'},
                {'name': '业务负责人确认', 'order': 2, 'approver_type': 'role', 'approver_value': 'platform-admin'},
                {'name': '运维值班确认', 'order': 3, 'approver_type': 'group', 'approver_value': 'ops-team'},
            ],
        )
        flow_prod_access = self.upsert_flow(
            name='事务工单 · 生产权限开通审批',
            environment='prod',
            description='面向生产访问与权限开通，强调安全、DBA 与平台双确认。',
            nodes=[
                {'name': '安全负责人确认', 'order': 1, 'approver_type': 'role', 'approver_value': 'security-admin'},
                {'name': 'DBA 值班确认', 'order': 2, 'approver_type': 'group', 'approver_value': 'dba-team'},
                {'name': '平台负责人确认', 'order': 3, 'approver_type': 'user', 'approver_value': 'ops-admin'},
            ],
        )
        flow_prod_incident = self.upsert_flow(
            name='事务工单 · 故障应急审批',
            environment='prod',
            description='面向线上故障处置，保留值班负责人快速确认链路。',
            nodes=[
                {'name': '值班经理确认', 'order': 1, 'approver_type': 'user', 'approver_value': 'ops-admin'},
                {'name': '业务接口人同步', 'order': 2, 'approver_type': 'group', 'approver_value': 'ops-team'},
            ],
        )
        flow_inspection = self.upsert_flow(
            name='事务工单 · 巡检维护审批',
            environment='test',
            description='面向巡检、维护与例行操作，适合测试与预发布场景。',
            nodes=[
                {'name': '执行人自检', 'order': 1, 'approver_type': 'user', 'approver_value': 'lisi'},
                {'name': '平台值班确认', 'order': 2, 'approver_type': 'user', 'approver_value': 'ops-admin'},
            ],
        )

        tickets = [
            {
                'title': '生产数据库白名单开通',
                'ticket_type': TransactionTicket.TYPE_ACCESS,
                'priority': TransactionTicket.PRIORITY_HIGH,
                'business_line': SYSTEM_TRADE,
                'environment': 'prod',
                'approval_flow': flow_prod_access,
                'owner': 'DBA 值班',
                'applicant': DEMO_OPERATOR,
                'window': '今晚 22:00 - 22:30',
                'description': '为结算链路排障开通临时只读白名单，执行后需在 30 分钟内回收权限。',
                'status': TransactionTicket.STATUS_PENDING,
                'created_at': now - timedelta(hours=1, minutes=20),
                'updated_at': now - timedelta(hours=1, minutes=20),
            },
            {
                'title': '夜间链路巡检任务',
                'ticket_type': TransactionTicket.TYPE_INSPECTION,
                'priority': TransactionTicket.PRIORITY_MEDIUM,
                'business_line': BIZ_DATA,
                'environment': 'test',
                'approval_flow': flow_inspection,
                'owner': '平台值班',
                'applicant': DEMO_OPERATOR,
                'window': '每日 23:00 - 23:30',
                'description': '对数据平台日志链路、消息堆积与采集 Agent 状态做例行巡检，异常结果需自动回传事件中心。',
                'status': TransactionTicket.STATUS_APPROVED,
                'created_at': now - timedelta(hours=6),
                'updated_at': now - timedelta(hours=4, minutes=40),
            },
            {
                'title': '网关限流策略紧急调整',
                'ticket_type': TransactionTicket.TYPE_INCIDENT,
                'priority': TransactionTicket.PRIORITY_HIGH,
                'business_line': SYSTEM_TRADE,
                'environment': 'prod',
                'approval_flow': flow_prod_incident,
                'owner': '应用网关值班',
                'applicant': DEMO_OPERATOR,
                'window': '立即执行',
                'description': '针对活动流量突增临时调整网关限流阈值，并同步观察 5 分钟错误率变化。',
                'status': TransactionTicket.STATUS_PROCESSING,
                'created_at': now - timedelta(hours=3, minutes=10),
                'updated_at': now - timedelta(hours=2, minutes=35),
            },
            {
                'title': '订单服务配置修正',
                'ticket_type': TransactionTicket.TYPE_CHANGE,
                'priority': TransactionTicket.PRIORITY_LOW,
                'business_line': BIZ_INFRA,
                'environment': 'prod',
                'approval_flow': flow_prod_change,
                'owner': '平台运维',
                'applicant': DEMO_OPERATOR,
                'window': '周三 20:00 - 20:20',
                'description': '修正订单服务发布后的连接池参数与限流配置，变更完成后需做一次健康检查回归。',
                'status': TransactionTicket.STATUS_DONE,
                'created_at': now - timedelta(days=1, hours=3),
                'updated_at': now - timedelta(days=1, hours=2, minutes=20),
            },
        ]

        active_titles = [item['title'] for item in tickets]
        TransactionTicket.objects.filter(
            applicant=DEMO_OPERATOR,
            title__startswith='示例 · ',
        ).delete()
        TransactionTicket.objects.filter(
            applicant=DEMO_OPERATOR,
        ).exclude(title__in=active_titles).delete()

        for item in tickets:
            self.upsert_ticket(item)

        count = TransactionTicket.objects.filter(applicant=DEMO_OPERATOR, title__in=active_titles).count()
        self.stdout.write(self.style.SUCCESS(f'事务工单演示数据生成完成，共 {count} 条。'))

    def upsert_flow(self, *, name, environment, description, nodes):
        flow, _ = DeploymentApprovalFlow.objects.update_or_create(
            name=name,
            defaults={
                'environment': environment,
                'description': description,
                'is_active': True,
                'created_by': DEMO_OPERATOR,
            },
        )
        flow.nodes.all().delete()
        DeploymentApprovalNode.objects.bulk_create([
            DeploymentApprovalNode(
                flow=flow,
                name=item['name'],
                order=item['order'],
                approver_type=item['approver_type'],
                approver_value=item['approver_value'],
            )
            for item in nodes
        ])
        return flow

    def upsert_ticket(self, payload):
        created_at = payload.pop('created_at')
        updated_at = payload.pop('updated_at')
        ticket, _ = TransactionTicket.objects.update_or_create(
            title=payload['title'],
            applicant=payload['applicant'],
            defaults=payload,
        )
        TransactionTicket.objects.filter(pk=ticket.pk).update(created_at=created_at, updated_at=updated_at)
        return ticket
