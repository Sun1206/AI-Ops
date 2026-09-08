from pathlib import Path

from django.apps import AppConfig


class OpsConfig(AppConfig):
    name = 'ops'
    path = str(Path(__file__).resolve().parent)

    def ready(self):
        from .observability_scheduler import start_observability_history_scheduler

        start_observability_history_scheduler()
