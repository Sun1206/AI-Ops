from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'ci-types', views.CITypeViewSet)
router.register(r'config-items', views.ConfigItemViewSet)
router.register(r'ci-relations', views.CIRelationViewSet)
router.register(r'cost-records', views.CostRecordViewSet)
router.register(r'resource-requests', views.ResourceRequestViewSet)
router.register(r'resource-nodes', views.ResourceNodeViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/stats/', views.cmdb_dashboard, name='cmdb-dashboard'),
    path('topology/data/', views.cmdb_topology, name='cmdb-topology'),
    path('cost/report/', views.cmdb_cost_report, name='cmdb-cost-report'),
    path('optimization/suggestions/', views.cmdb_optimization, name='cmdb-optimization'),
]
