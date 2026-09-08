from django.db import migrations


PERMISSION_RENAMES = [
    (
        'ops.observability.firemap.view',
        'ops.observability.system_posture.view',
        '查看系统态势',
        '查看业务系统健康、SLA 总览、层级下钻与依赖影响',
    ),
    (
        'ops.observability.firemap.manage',
        'ops.observability.system_posture.manage',
        '管理系统态势',
        '新增、编辑、删除系统态势卡片与环境分组',
    ),
]


def migrate_system_posture_permissions(apps, schema_editor):
    PermissionDefinition = apps.get_model('rbac', 'PermissionDefinition')
    Role = apps.get_model('rbac', 'Role')

    for old_code, new_code, name, description in PERMISSION_RENAMES:
        new_permission, _ = PermissionDefinition.objects.update_or_create(
            code=new_code,
            defaults={'name': name, 'category': 'ops', 'description': description, 'is_builtin': True},
        )
        try:
            old_permission = PermissionDefinition.objects.get(code=old_code)
        except PermissionDefinition.DoesNotExist:
            continue

        for role in Role.objects.filter(permissions=old_permission):
            role.permissions.add(new_permission)
        old_permission.delete()


def restore_system_posture_permissions(apps, schema_editor):
    PermissionDefinition = apps.get_model('rbac', 'PermissionDefinition')
    Role = apps.get_model('rbac', 'Role')

    for old_code, new_code, name, description in PERMISSION_RENAMES:
        old_permission, _ = PermissionDefinition.objects.update_or_create(
            code=old_code,
            defaults={'name': name, 'category': 'ops', 'description': description, 'is_builtin': True},
        )
        try:
            new_permission = PermissionDefinition.objects.get(code=new_code)
        except PermissionDefinition.DoesNotExist:
            continue

        for role in Role.objects.filter(permissions=new_permission):
            role.permissions.add(old_permission)


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0039_systemposturesystem_table'),
        ('rbac', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_system_posture_permissions, restore_system_posture_permissions),
    ]
