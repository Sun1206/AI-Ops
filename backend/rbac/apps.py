from django.apps import AppConfig
from django.db.models.signals import post_migrate


class RbacConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rbac'
    verbose_name = 'RBAC 权限'

    def ready(self):
        post_migrate.connect(sync_builtin_rbac, sender=self)


def sync_builtin_rbac(**kwargs):
    from .services import ensure_builtin_rbac, ensure_default_superuser

    ensure_builtin_rbac()
    ensure_default_superuser()
