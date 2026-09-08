from django.contrib import admin

from .models import PermissionDefinition, Role, UserGroup


@admin.register(PermissionDefinition)
class PermissionDefinitionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'is_builtin', 'updated_at')
    list_filter = ('category', 'is_builtin')
    search_fields = ('code', 'name', 'description')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_builtin', 'updated_at')
    list_filter = ('is_builtin',)
    search_fields = ('code', 'name', 'description')
    filter_horizontal = ('permissions', 'users')


@admin.register(UserGroup)
class UserGroupAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_builtin', 'updated_at')
    list_filter = ('is_builtin',)
    search_fields = ('code', 'name', 'description')
    filter_horizontal = ('roles', 'users')
