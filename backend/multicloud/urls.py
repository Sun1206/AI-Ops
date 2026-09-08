from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('credentials', views.CloudCredentialViewSet, basename='multicloud-credential')
router.register('environments', views.CloudEnvironmentViewSet, basename='multicloud-environment')
router.register('assets', views.CloudAssetViewSet, basename='multicloud-asset')
router.register('sync-tasks', views.CloudSyncTaskViewSet, basename='multicloud-task')

urlpatterns = [
    path('', include(router.urls)),
    path('overview/', views.overview_view, name='multicloud-overview'),
    path('catalog/', views.catalog_view, name='multicloud-catalog'),
    path('topology/', views.topology_view, name='multicloud-topology'),
    path('cost-trend/', views.cost_trend_view, name='multicloud-cost-trend'),
    path('batch-sync/', views.batch_sync_view, name='multicloud-batch-sync'),
    path('batch-actions/', views.batch_action_view, name='multicloud-batch-actions'),
]
