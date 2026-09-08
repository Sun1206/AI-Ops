from django.apps import AppConfig


class CmdbConfig(AppConfig):
    name = 'cmdb'

    def ready(self):
        from . import signals  # noqa: F401
