from django.core.management.base import BaseCommand

from ops.host_task_schedules import run_due_schedules, run_scheduler_loop


class Command(BaseCommand):
    help = '运行主机定时任务调度器，触发到点的主机编排任务'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='仅扫描一次到期编排并立即退出')
        parser.add_argument('--interval', type=int, default=None, help='轮询间隔秒数，默认读取 settings.HOST_TASK_SCHEDULER_POLL_SECONDS')
        parser.add_argument('--limit', type=int, default=20, help='单次扫描最多触发的编排数量')
        parser.add_argument('--actor', type=str, default='system-scheduler', help='调度器写入执行记录时使用的触发人标识')

    def handle(self, *args, **options):
        once = options['once']
        interval = options.get('interval')
        limit = int(options.get('limit') or 20)
        actor = options.get('actor') or 'system-scheduler'

        if once:
            result = run_due_schedules(limit=limit, actor=actor)
            self.stdout.write(self.style.SUCCESS(
                f"扫描完成：待执行 {result['due_count']}，触发 {result['triggered']}，跳过 {result['skipped']}"
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f'主机定时任务调度器已启动，轮询间隔={interval or "settings 默认值"}秒，单次上限={limit}'
        ))
        run_scheduler_loop(interval_seconds=interval, limit=limit, actor=actor)
