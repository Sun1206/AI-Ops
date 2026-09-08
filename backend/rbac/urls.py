from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views


router = DefaultRouter()
router.register('users', views.UserViewSet, basename='rbac-user')
router.register('roles', views.RoleViewSet, basename='rbac-role')
router.register('groups', views.UserGroupViewSet, basename='rbac-group')
router.register('permissions', views.PermissionDefinitionViewSet, basename='rbac-permission')

urlpatterns = [
    path('auth/login/', views.login_view, name='rbac-login'),
    path('auth/logout/', views.logout_view, name='rbac-logout'),
    path('auth/me/', views.current_user_view, name='rbac-me'),
    path('auth/sync/', views.sync_permissions_view, name='rbac-sync'),
    path('module-settings/', views.system_module_settings_view, name='rbac-module-settings'),
    path('', include(router.urls)),
]
