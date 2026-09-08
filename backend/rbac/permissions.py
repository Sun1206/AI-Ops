from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated

from .services import DEMO_ACCOUNT_MUTATION_MESSAGE, is_demo_account, user_has_permissions


class RBACPermission(BasePermission):
    message = '当前用户没有执行此操作的权限。'
    required_permissions = ()

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        action = getattr(view, 'action', None)
        allowed_actions = set(getattr(view, 'demo_account_allowed_actions', set()) or [])
        allow_demo_write = bool(getattr(self, 'allow_demo_write', False) or getattr(view, 'demo_account_allow_write', False))
        if (
            is_demo_account(request.user)
            and request.method.upper() not in SAFE_METHODS
            and not allow_demo_write
            and action not in allowed_actions
        ):
            self.message = DEMO_ACCOUNT_MUTATION_MESSAGE
            return False

        codes = getattr(self, 'required_permissions', ())
        if not codes and hasattr(view, 'get_required_permissions'):
            codes = view.get_required_permissions()
        if isinstance(codes, str):
            codes = [codes]
        if not codes:
            return True
        if user_has_permissions(request.user, codes):
            return True
        self.message = f'缺少权限: {", ".join(codes)}'
        return False


class RBACPermissionMixin:
    permission_classes = [IsAuthenticated, RBACPermission]
    rbac_permissions = {}

    def get_required_permissions(self):
        mapping = getattr(self, 'rbac_permissions', {}) or {}
        action = getattr(self, 'action', None)
        codes = mapping.get(action, mapping.get('*', []))
        if isinstance(codes, str):
            return [codes]
        return list(codes or [])


def build_rbac_permission(*codes, allow_demo_write=False):
    class ViewRBACPermission(RBACPermission):
        required_permissions = codes

    ViewRBACPermission.allow_demo_write = allow_demo_write

    return ViewRBACPermission
