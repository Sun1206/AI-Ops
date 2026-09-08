from django.contrib.auth import authenticate, get_user_model
from rest_framework import filters, status, viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from eventwall.mixins import EventWallModelViewSetMixin
from eventwall.models import EventRecord
from eventwall.services import record_event

from .models import PermissionDefinition, Role, SystemModuleSetting, UserGroup
from .permissions import RBACPermissionMixin, build_rbac_permission
from .serializers import (
    LoginSerializer,
    PermissionDefinitionSerializer,
    RoleSerializer,
    UserGroupSerializer,
    UserSerializer,
)
from .services import (
    DEMO_ACCOUNT_MUTATION_MESSAGE,
    ensure_builtin_rbac,
    ensure_default_superuser,
    ensure_system_module_settings,
    get_system_module_settings,
    is_demo_account,
    user_has_permissions,
)


User = get_user_model()


class UserViewSet(EventWallModelViewSetMixin, RBACPermissionMixin, viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    event_module = 'rbac'
    event_resource_type = 'rbac_user'
    event_resource_label = '用户'
    event_resource_name_fields = ('username',)
    event_exclude_fields = ('password',)
    rbac_permissions = {
        'list': ['rbac.user.view'],
        'retrieve': ['rbac.user.view'],
        'create': ['rbac.user.manage'],
        'update': ['rbac.user.manage'],
        'partial_update': ['rbac.user.manage'],
        'destroy': ['rbac.user.manage'],
        'reset_password': ['rbac.user.manage'],
    }

    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        user = self.get_object()
        password = request.data.get('password', '').strip()
        if not password:
            return Response({'detail': '新密码不能为空。'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(instance=user, data={'password': password}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_event(
            request=request,
            module='rbac',
            category='security',
            action='reset_password',
            title='重置用户密码',
            summary=f'已重置用户 {user.username} 的密码',
            resource_type='rbac_user',
            resource_id=user.id,
            resource_name=user.username,
            severity=EventRecord.SEVERITY_WARNING,
            correlation_id=f'rbac-user:{user.id}',
            metadata={'target_user': user.username},
        )
        return Response({'success': True, 'message': f'已重置 {user.username} 的密码。'})


class RoleViewSet(EventWallModelViewSetMixin, RBACPermissionMixin, viewsets.ModelViewSet):
    queryset = Role.objects.prefetch_related('permissions').all().order_by('name')
    serializer_class = RoleSerializer
    pagination_class = None
    filter_backends = [filters.SearchFilter]
    search_fields = ['code', 'name', 'description']
    event_module = 'rbac'
    event_resource_type = 'rbac_role'
    event_resource_label = '角色'
    event_resource_name_fields = ('name', 'code')
    rbac_permissions = {
        'list': ['rbac.role.view'],
        'retrieve': ['rbac.role.view'],
        'create': ['rbac.role.manage'],
        'update': ['rbac.role.manage'],
        'partial_update': ['rbac.role.manage'],
        'destroy': ['rbac.role.manage'],
    }

    def perform_destroy(self, instance):
        if instance.is_builtin:
            raise ValidationError('内置角色不允许删除。')
        super().perform_destroy(instance)


class UserGroupViewSet(EventWallModelViewSetMixin, RBACPermissionMixin, viewsets.ModelViewSet):
    queryset = UserGroup.objects.prefetch_related('roles', 'users').all().order_by('name')
    serializer_class = UserGroupSerializer
    pagination_class = None
    filter_backends = [filters.SearchFilter]
    search_fields = ['code', 'name', 'description']
    event_module = 'rbac'
    event_resource_type = 'rbac_group'
    event_resource_label = '用户组'
    event_resource_name_fields = ('name', 'code')
    rbac_permissions = {
        'list': ['rbac.group.view'],
        'retrieve': ['rbac.group.view'],
        'create': ['rbac.group.manage'],
        'update': ['rbac.group.manage'],
        'partial_update': ['rbac.group.manage'],
        'destroy': ['rbac.group.manage'],
    }

    def perform_destroy(self, instance):
        if instance.is_builtin:
            raise ValidationError('内置用户组不允许删除。')
        super().perform_destroy(instance)


class PermissionDefinitionViewSet(RBACPermissionMixin, viewsets.ReadOnlyModelViewSet):
    queryset = PermissionDefinition.objects.all().order_by('sort_order', 'code')
    serializer_class = PermissionDefinitionSerializer
    pagination_class = None
    filter_backends = [filters.SearchFilter]
    search_fields = ['code', 'name', 'description', 'category']
    rbac_permissions = {
        'list': ['rbac.permission.view'],
        'retrieve': ['rbac.permission.view'],
    }


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def system_module_settings_view(request):
    ensure_system_module_settings()

    if request.method == 'GET':
        return Response(get_system_module_settings())

    if is_demo_account(request.user):
        return Response({'detail': DEMO_ACCOUNT_MUTATION_MESSAGE}, status=status.HTTP_403_FORBIDDEN)

    if not user_has_permissions(request.user, ['rbac.module.manage']):
        return Response({'detail': '当前用户没有执行此操作的权限。'}, status=status.HTTP_403_FORBIDDEN)

    payload = request.data.get('modules', request.data) if isinstance(request.data, dict) else request.data
    if not isinstance(payload, list):
        return Response({'detail': '模块配置必须是列表。'}, status=status.HTTP_400_BAD_REQUEST)

    enabled_map = {
        item.get('code'): bool(item.get('enabled'))
        for item in payload
        if isinstance(item, dict) and item.get('code')
    }
    setting_map = {item.code: item for item in SystemModuleSetting.objects.all()}
    updated_items = []
    for item in get_system_module_settings():
        code = item['code']
        setting = setting_map.get(code)
        if not setting:
            continue
        if item['required']:
            setting.enabled = True
        elif code in enabled_map:
            setting.enabled = enabled_map[code]
        setting.updated_by = request.user.username
        setting.save(update_fields=['enabled', 'updated_by', 'updated_at'])
        updated_items.append({
            **item,
            'enabled': setting.enabled,
            'updated_by': setting.updated_by,
            'updated_at': setting.updated_at,
        })

    record_event(
        request=request,
        module='rbac',
        category='system',
        action='update_module_settings',
        title='更新系统模块显示配置',
        summary=f'已更新系统模块显示配置，共 {len(updated_items)} 项',
        resource_type='rbac_system_module_setting',
        resource_id='module-settings',
        resource_name='系统模块配置',
        severity=EventRecord.SEVERITY_INFO,
        correlation_id='rbac-system-module-settings',
        metadata={'updated_count': len(updated_items)},
    )
    return Response({'success': True, 'data': get_system_module_settings()})


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    ensure_builtin_rbac()
    ensure_default_superuser()
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(
        username=serializer.validated_data['username'],
        password=serializer.validated_data['password'],
    )
    if not user:
        return Response({'detail': '用户名或密码错误。'}, status=status.HTTP_400_BAD_REQUEST)
    if not user.is_active:
        return Response({'detail': '用户已被禁用。'}, status=status.HTTP_403_FORBIDDEN)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'user': UserSerializer(user).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    token = Token.objects.filter(user=request.user).first()
    if token:
        token.delete()
    return Response({'success': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user_view(request):
    ensure_builtin_rbac()
    return Response(UserSerializer(request.user).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, build_rbac_permission('rbac.permission.view')])
def sync_permissions_view(request):
    ensure_builtin_rbac()
    record_event(
        request=request,
        module='rbac',
        category='system',
        action='sync_permissions',
        title='同步内置权限',
        summary='内置权限与角色已同步完成',
        resource_type='rbac_permission_registry',
        resource_id='builtin',
        resource_name='内置权限字典',
        severity=EventRecord.SEVERITY_INFO,
        correlation_id='rbac-permission-registry',
    )
    return Response({'success': True, 'message': '内置权限与角色已同步。'})
