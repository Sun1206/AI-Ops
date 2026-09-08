from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views


router = DefaultRouter()
router.register('stacks', views.TerraformStackViewSet, basename='iac-stack')

urlpatterns = [
    path('', include(router.urls)),
    path('catalog/', views.terraform_catalog_view, name='iac-catalog'),
    path('render/', views.terraform_render_view, name='iac-render'),
    path('bundle/', views.terraform_bundle_view, name='iac-bundle'),
]
