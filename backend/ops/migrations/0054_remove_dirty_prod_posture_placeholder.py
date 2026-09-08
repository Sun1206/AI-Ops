from django.db import migrations


def remove_dirty_prod_posture_placeholder(apps, schema_editor):
    SystemPostureSystem = apps.get_model('ops', 'SystemPostureSystem')
    SystemPostureSystem.objects.filter(
        environment='prod',
        name__regex=r'^\?+$',
        created_by='system',
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0053_update_ecommerce_success_rate_and_409_impact'),
    ]

    operations = [
        migrations.RunPython(remove_dirty_prod_posture_placeholder, migrations.RunPython.noop),
    ]
