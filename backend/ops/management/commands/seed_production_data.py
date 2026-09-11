from django.core.management.base import BaseCommand
from django.db import transaction

from ops.management.production_seed.aiops_data import seed_aiops
from ops.management.production_seed.alerting import seed_alerting
from ops.management.production_seed.audit_data import seed_audit_data
from ops.management.production_seed.common import SeedStats, resolve_base_objects
from ops.management.production_seed.log_data import seed_log_data
from ops.management.production_seed.observability import seed_observability
from ops.management.production_seed.runtime_data import seed_runtime_data
from ops.management.production_seed.task_resources import seed_task_resources


class Command(BaseCommand):
    help = '补充可重复执行的生产化数据，不删除现有记录'

    @transaction.atomic
    def handle(self, *args, **options):
        stats = SeedStats()
        base = resolve_base_objects(stats)
        runtime_context = seed_runtime_data(stats, base)
        task_context = seed_task_resources(stats, base)
        alert_context = seed_alerting(stats, base)
        obs_context = seed_observability(stats, base)
        seed_log_data(stats, runtime_context)
        seed_aiops(stats, base, task_context, alert_context, obs_context)
        seed_audit_data(stats, base)
        self.stdout.write(self.style.SUCCESS(
            f'Production seed complete: created={stats.created}, reused={stats.reused}'
        ))
