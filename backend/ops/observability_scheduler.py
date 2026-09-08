from __future__ import annotations

import logging
import os
import sys
import threading
import time
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

_scheduler_lock = threading.Lock()
_scheduler_started = False


def _seconds_until_next_hour():
    now = timezone.localtime()
    next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    return max(1, int((next_hour - now).total_seconds()))


def scheduler_should_autostart():
    blocked = {'test', 'makemigrations', 'migrate', 'collectstatic', 'shell'}
    if any(item in sys.argv for item in blocked):
        return False
    if os.environ.get('RUN_MAIN') == 'false':
        return False
    return True


def run_observability_history_scheduler_loop():
    logger.info('observability history scheduler is disabled in the open-source build')


def start_observability_history_scheduler():
    global _scheduler_started
    if _scheduler_started or not scheduler_should_autostart():
        return False
    with _scheduler_lock:
        if _scheduler_started:
            return False
        _scheduler_started = True
        logger.info('observability history scheduler disabled in the open-source build')
        return False
