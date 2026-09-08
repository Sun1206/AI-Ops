from __future__ import annotations

import logging
import math
import sys
import time
from datetime import timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Host, HostTask, HostTaskSchedule, HostTaskScheduleExecution

logger = logging.getLogger(__name__)

CRON_MONTH_ALIASES = {
    'jan': 1,
    'feb': 2,
    'mar': 3,
    'apr': 4,
    'may': 5,
    'jun': 6,
    'jul': 7,
    'aug': 8,
    'sep': 9,
    'oct': 10,
    'nov': 11,
    'dec': 12,
}
CRON_WEEKDAY_ALIASES = {
    'sun': 0,
    'mon': 1,
    'tue': 2,
    'wed': 3,
    'thu': 4,
    'fri': 5,
    'sat': 6,
}


class CronExpressionError(ValueError):
    pass


def _get_value(source, key, default=None):
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _normalize_datetime(value, tz_name):
    if not value:
        return None
    current_tz = ZoneInfo(tz_name or settings.TIME_ZONE)
    if timezone.is_naive(value):
        value = timezone.make_aware(value, current_tz)
    return value.astimezone(current_tz)


def _cron_value(value, aliases=None):
    value = str(value).strip().lower()
    if aliases and value in aliases:
        return aliases[value]
    return int(value)


def _expand_cron_field(field, minimum, maximum, aliases=None):
    values = set()
    for part in str(field).split(','):
        part = part.strip().lower()
        if not part:
            raise CronExpressionError('Cron 字段不能为空')
        if part == '*':
            values.update(range(minimum, maximum + 1))
            continue
        if '/' in part:
            base, step_text = part.split('/', 1)
            step = int(step_text)
            if step <= 0:
                raise CronExpressionError('Cron 步长必须大于 0')
        else:
            base = part
            step = 1

        if base in ('', '*'):
            start, end = minimum, maximum
        elif '-' in base:
            start_text, end_text = base.split('-', 1)
            start = _cron_value(start_text, aliases)
            end = _cron_value(end_text, aliases)
        else:
            start = end = _cron_value(base, aliases)

        if aliases is CRON_WEEKDAY_ALIASES:
            if start == 7:
                start = 0
            if end == 7:
                end = 0
        if start < minimum or end > maximum:
            raise CronExpressionError(f'Cron 字段取值需位于 {minimum}-{maximum}')

        if aliases is CRON_WEEKDAY_ALIASES and start > end:
            for item in list(range(start, maximum + 1, step)) + list(range(minimum, end + 1, step)):
                values.add(0 if item == 7 else item)
            continue

        if start > end:
            raise CronExpressionError('Cron 区间起始值不能大于结束值')
        values.update(range(start, end + 1, step))

    if aliases is CRON_WEEKDAY_ALIASES:
        return {0 if item == 7 else item for item in values}
    return values


def validate_cron_expression(expression):
    parts = str(expression or '').split()
    if len(parts) != 5:
        raise CronExpressionError('Cron 表达式需要 5 段：分 时 日 月 周')
    minute, hour, day_of_month, month, day_of_week = parts
    return {
        'minute': _expand_cron_field(minute, 0, 59),
        'hour': _expand_cron_field(hour, 0, 23),
        'day_of_month': _expand_cron_field(day_of_month, 1, 31),
        'month': _expand_cron_field(month, 1, 12, CRON_MONTH_ALIASES),
        'day_of_week': _expand_cron_field(day_of_week, 0, 7, CRON_WEEKDAY_ALIASES),
    }


def _cron_matches(current, parsed):
    day_match = current.day in parsed['day_of_month']
    cron_weekday = (current.weekday() + 1) % 7
    weekday_match = cron_weekday in parsed['day_of_week']
    all_days = len(parsed['day_of_month']) == 31
    all_weekdays = len(parsed['day_of_week']) == 7
    if all_days and all_weekdays:
        day_ok = True
    elif all_days:
        day_ok = weekday_match
    elif all_weekdays:
        day_ok = day_match
    else:
        day_ok = day_match or weekday_match
    return (
        current.minute in parsed['minute']
        and current.hour in parsed['hour']
        and current.month in parsed['month']
        and day_ok
    )


def compute_next_run(source, reference_time=None, include_current=False):
    schedule_type = _get_value(source, 'schedule_type', HostTaskSchedule.SCHEDULE_TYPE_CRON)
    timezone_name = _get_value(source, 'timezone', settings.TIME_ZONE)
    now = reference_time or timezone.now()
    tz = ZoneInfo(timezone_name or settings.TIME_ZONE)
    current = now.astimezone(tz)

    if schedule_type == HostTaskSchedule.SCHEDULE_TYPE_ONCE:
        run_at = _normalize_datetime(_get_value(source, 'run_at'), timezone_name)
        if not run_at:
            return None
        if include_current and run_at >= current:
            return run_at.astimezone(timezone.get_current_timezone())
        if run_at > current:
            return run_at.astimezone(timezone.get_current_timezone())
        return None

    if schedule_type == HostTaskSchedule.SCHEDULE_TYPE_INTERVAL:
        interval_seconds = int(_get_value(source, 'interval_seconds') or 0)
        if interval_seconds <= 0:
            return None
        anchor = _normalize_datetime(_get_value(source, 'run_at'), timezone_name) or current
        if anchor > current:
            return anchor.astimezone(timezone.get_current_timezone())
        elapsed_seconds = max((current - anchor).total_seconds(), 0)
        steps = math.floor(elapsed_seconds / interval_seconds) + 1
        next_run = anchor + timedelta(seconds=steps * interval_seconds)
        return next_run.astimezone(timezone.get_current_timezone())

    parsed = validate_cron_expression(_get_value(source, 'cron_expression', ''))
    cursor = current.replace(second=0, microsecond=0)
    if not include_current:
        cursor += timedelta(minutes=1)
    max_checks = 60 * 24 * 370
    for _ in range(max_checks):
        if _cron_matches(cursor, parsed):
            return cursor.astimezone(timezone.get_current_timezone())
        cursor += timedelta(minutes=1)
    return None


def preview_next_runs(source, count=5, reference_time=None):
    schedule_type = _get_value(source, 'schedule_type', HostTaskSchedule.SCHEDULE_TYPE_CRON)
    if schedule_type == HostTaskSchedule.SCHEDULE_TYPE_INTERVAL:
        first_run = compute_next_run(source, reference_time=reference_time)
        if not first_run:
            return []
        interval_seconds = int(_get_value(source, 'interval_seconds') or 0)
        return [first_run + timedelta(seconds=index * interval_seconds) for index in range(max(count, 0))]

    if schedule_type == HostTaskSchedule.SCHEDULE_TYPE_ONCE:
        run_at = compute_next_run(source, reference_time=reference_time)
        return [run_at] if run_at else []

    result = []
    cursor = reference_time or timezone.now()
    for _ in range(count):
        next_run = compute_next_run(source, reference_time=cursor, include_current=False)
        if not next_run:
            break
        result.append(next_run)
        cursor = next_run + timedelta(minutes=1)
    return result


def resolve_schedule_hosts(schedule):
    from .host_tasks import build_host_target_queryset

    host_ids = list(dict.fromkeys(int(item) for item in (_get_value(schedule, 'target_host_ids', []) or []) if item))
    selection_filters = _get_value(schedule, 'selection_filters', {}) or {}
    host_map = {}
    for host in Host.objects.filter(id__in=host_ids):
        host_map[host.id] = host
    queryset = build_host_target_queryset(selection_filters)
    for host in queryset:
        host_map[host.id] = host
    return list(host_map.values())


def build_schedule_snapshot(hosts: Iterable[Host]):
    host_list = list(hosts)
    return [
        {
            'id': host.id,
            'hostname': host.hostname,
            'ip_address': host.ip_address,
            'business_line': host.business_line,
            'environment': host.environment,
            'status': host.status,
        }
        for host in host_list
    ]


def sync_schedule_targets(schedule):
    hosts = resolve_schedule_hosts(schedule)
    schedule.target_count = len(hosts)
    schedule.target_snapshot = build_schedule_snapshot(hosts)
    return hosts


def _running_schedule_exists(schedule):
    return schedule.generated_tasks.filter(status__in=[HostTask.STATUS_PENDING, HostTask.STATUS_RUNNING]).exists()


def _update_schedule_after_failure(schedule, summary, when=None):
    when = when or timezone.now()
    schedule.last_run_at = when
    schedule.last_status = HostTask.STATUS_FAILED
    schedule.consecutive_failures += 1
    schedule.total_run_count += 1
    schedule.last_error = (summary or '')[:255]
    if schedule.schedule_type == HostTaskSchedule.SCHEDULE_TYPE_ONCE:
        schedule.enabled = False
        schedule.next_run_at = None
    else:
        schedule.next_run_at = compute_next_run(schedule, reference_time=when)
    schedule.save(update_fields=['last_run_at', 'last_status', 'consecutive_failures', 'total_run_count', 'last_error', 'enabled', 'next_run_at', 'updated_at'])


def _prepare_schedule_fields(schedule, scheduled_run, when):
    schedule.last_run_at = when
    schedule.total_run_count += 1
    if scheduled_run:
        if schedule.schedule_type == HostTaskSchedule.SCHEDULE_TYPE_ONCE:
            schedule.enabled = False
            schedule.next_run_at = None
        else:
            schedule.next_run_at = compute_next_run(schedule, reference_time=when)
    schedule.save(update_fields=['last_run_at', 'total_run_count', 'enabled', 'next_run_at', 'updated_at'])


def trigger_schedule(schedule, actor='system', trigger_source=HostTaskScheduleExecution.TRIGGER_SCHEDULER, scheduled_run=False):
    from .host_tasks import start_host_task

    hosts = sync_schedule_targets(schedule)
    schedule.save(update_fields=['target_count', 'target_snapshot', 'updated_at'])
    now = timezone.now()

    if scheduled_run and schedule.overlap_policy == HostTaskSchedule.OVERLAP_SKIP and _running_schedule_exists(schedule):
        if schedule.schedule_type == HostTaskSchedule.SCHEDULE_TYPE_ONCE:
            schedule.enabled = False
            schedule.next_run_at = None
        else:
            schedule.next_run_at = compute_next_run(schedule, reference_time=now)
        schedule.save(update_fields=['enabled', 'next_run_at', 'updated_at'])
        return None, None

    if not hosts:
        execution = HostTaskScheduleExecution.objects.create(
            schedule=schedule,
            trigger_source=trigger_source,
            status=HostTask.STATUS_FAILED,
            summary='未匹配到可执行主机',
            error_message='未匹配到可执行主机',
            requested_by=actor,
            target_count=0,
            started_at=now,
            finished_at=now,
        )
        _update_schedule_after_failure(schedule, execution.summary, when=now)
        return execution, None

    with transaction.atomic():
        task = HostTask.objects.create(
            name=schedule.name,
            task_type=schedule.task_type,
            description=schedule.description,
            payload=dict(schedule.payload or {}),
            selection_filters=dict(schedule.selection_filters or {}),
            execution_mode=schedule.execution_mode,
            execution_strategy=schedule.execution_strategy,
            timeout_seconds=schedule.timeout_seconds,
            schedule=schedule,
            trigger_source=HostTask.TRIGGER_SOURCE_SCHEDULE,
            lifecycle_status=HostTask.LIFECYCLE_PENDING_EXECUTION,
            risk_level=HostTask.RISK_MEDIUM if schedule.task_type in [HostTask.TASK_RUN_COMMAND, HostTask.TASK_RUN_PLAYBOOK] else HostTask.RISK_LOW,
            source_context={'source': 'schedule', 'schedule_id': schedule.id, 'trigger_source': trigger_source},
            created_by=actor,
            summary='定时任务已创建，等待后台执行',
        )
        task.correlation_id = f'host-task-schedule:{schedule.id}'
        task.save(update_fields=['correlation_id'])
        execution = HostTaskScheduleExecution.objects.create(
            schedule=schedule,
            host_task=task,
            trigger_source=trigger_source,
            status=HostTask.STATUS_RUNNING,
            summary='已创建执行任务，等待后台执行',
            requested_by=actor,
            target_count=len(hosts),
            started_at=now,
        )
        _prepare_schedule_fields(schedule, scheduled_run=scheduled_run, when=now)

    start_host_task(task, hosts)
    return execution, task


def sync_schedule_after_task(task):
    if not getattr(task, 'schedule_id', None):
        return
    schedule = task.schedule
    success_like = task.status in [HostTask.STATUS_SUCCESS, HostTask.STATUS_PARTIAL]
    schedule.last_status = task.status
    schedule.last_error = '' if success_like else (task.summary or '')[:255]
    schedule.consecutive_failures = 0 if success_like else schedule.consecutive_failures + 1
    schedule.last_run_at = task.started_at or schedule.last_run_at or timezone.now()
    schedule.save(update_fields=['last_status', 'last_error', 'consecutive_failures', 'last_run_at', 'updated_at'])

    execution = getattr(task, 'schedule_execution', None)
    if execution:
        execution.status = task.status
        execution.summary = task.summary
        execution.target_count = task.target_count
        execution.success_count = task.success_count
        execution.failed_count = task.failed_count
        execution.skipped_count = task.skipped_count
        execution.started_at = task.started_at or execution.started_at
        execution.finished_at = task.finished_at or execution.finished_at
        execution.error_message = '' if success_like else (task.summary or '')[:255]
        execution.save(update_fields=['status', 'summary', 'target_count', 'success_count', 'failed_count', 'skipped_count', 'started_at', 'finished_at', 'error_message'])


def run_due_schedules(limit=20, actor='system-scheduler'):
    now = timezone.now()
    due_schedules = list(
        HostTaskSchedule.objects.filter(enabled=True, next_run_at__isnull=False, next_run_at__lte=now)
        .order_by('next_run_at', 'id')[:limit]
    )
    triggered = 0
    skipped = 0
    for schedule in due_schedules:
        execution, task = trigger_schedule(schedule, actor=actor, trigger_source=HostTaskScheduleExecution.TRIGGER_SCHEDULER, scheduled_run=True)
        if execution or task:
            triggered += 1
        else:
            skipped += 1
    return {
        'due_count': len(due_schedules),
        'triggered': triggered,
        'skipped': skipped,
        'checked_at': now,
    }


def run_scheduler_loop(interval_seconds=None, limit=20, actor='system-scheduler'):
    interval = int(interval_seconds or getattr(settings, 'HOST_TASK_SCHEDULER_POLL_SECONDS', 30))
    logger.info('host task scheduler loop started, interval=%s', interval)
    while True:
        try:
            result = run_due_schedules(limit=limit, actor=actor)
            logger.debug('host task scheduler checked due schedules: %s', result)
        except Exception:
            logger.exception('host task scheduler loop failed')
        time.sleep(max(interval, 5))


def scheduler_should_autostart():
    configured = getattr(settings, 'HOST_TASK_SCHEDULER_AUTOSTART', False)
    if not configured:
        return False
    if 'test' in sys.argv or 'makemigrations' in sys.argv or 'migrate' in sys.argv:
        return False
    return True
