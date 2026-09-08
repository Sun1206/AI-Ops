from django.core.management.base import BaseCommand
from django.db.models import Q

from eventwall.models import EventRecord
from multicloud.models import CloudAsset, CloudCredential, CloudEnvironment, CloudSyncTask
from ops.models import Alert, Deployment, Host, HostTask, HostTaskSchedule, TransactionTicket


class Command(BaseCommand):
    help = '清理非 CMDB 模块里会污染真实电商测试环境的电商演示数据'

    def handle(self, *args, **options):
        deleted = {}

        event_qs = EventRecord.objects.filter(
            Q(is_demo=True, metadata__hourly_demo_environment='电商测试环境-k3s')
            | Q(is_demo=True, environment='电商测试环境-k3s')
            | Q(is_demo=True, business_line__in=['电商', '电商线'])
        )
        deleted['event_records'] = event_qs.delete()[0]

        demo_hosts = [
            'order-api-ecs-01',
            'order-api-ecs-02',
            'order-perf-test-ecs',
            'feature-x-dev-ecs',
        ]
        demo_host_qs = Host.objects.filter(hostname__in=demo_hosts, business_line__in=['电商', '电商线'])
        Alert.objects.filter(Q(host__in=demo_host_qs) | Q(business_line__in=['电商', '电商线'], source__in=['APM', 'Prometheus', 'Zabbix'])).delete()
        deleted['hosts'] = demo_host_qs.delete()[0]

        deployment_qs = Deployment.objects.filter(
            business_line__in=['电商', '电商线'],
            app_name__in=['erp-platform', 'gateway-service', 'order-center'],
        )
        deleted['deployments'] = deployment_qs.delete()[0]

        ticket_qs = TransactionTicket.objects.filter(
            applicant='ops-demo',
            business_line__in=['电商', '电商线'],
        )
        deleted['transaction_tickets'] = ticket_qs.delete()[0]

        HostTask.objects.filter(selection_filters__business_line__in=['电商', '电商线']).delete()
        HostTaskSchedule.objects.filter(selection_filters__business_line__in=['电商', '电商线']).delete()

        env_qs = CloudEnvironment.objects.filter(
            Q(business_line__in=['电商', '电商线'])
            | Q(code__icontains='commerce')
            | Q(vpc_name__icontains='commerce')
        )
        credential_qs = CloudCredential.objects.filter(
            Q(demo_mode=True, name__icontains='电商')
            | Q(demo_mode=True, account_name__icontains='commerce')
            | Q(demo_mode=True, tags__team='commerce')
        )
        CloudAsset.objects.filter(environment__in=env_qs).delete()
        CloudSyncTask.objects.filter(Q(environment__in=env_qs) | Q(credential__in=credential_qs)).delete()
        deleted['cloud_environments'] = env_qs.delete()[0]
        deleted['cloud_credentials'] = credential_qs.delete()[0]

        for key, count in deleted.items():
            self.stdout.write(f'{key}: {count}')
        self.stdout.write(self.style.SUCCESS('电商演示数据清理完成'))
