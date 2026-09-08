from django.db import migrations, models
import django.db.models.deletion


def forwards(apps, schema_editor):
    Alert = apps.get_model('ops', 'Alert')
    AlertClaim = apps.get_model('ops', 'AlertClaim')
    for alert in Alert.objects.exclude(claimed_by='').exclude(claimed_by__isnull=True):
        claimant = (alert.claimed_by or '').strip()
        if not claimant:
            continue
        AlertClaim.objects.get_or_create(
            alert=alert,
            claimant=claimant,
            defaults={'claimed_at': alert.claimed_at or alert.updated_at or alert.created_at},
        )


def backwards(apps, schema_editor):
    Alert = apps.get_model('ops', 'Alert')
    AlertClaim = apps.get_model('ops', 'AlertClaim')
    for alert in Alert.objects.all():
        claim = AlertClaim.objects.filter(alert=alert).order_by('claimed_at', 'id').first()
        alert.claimed_by = claim.claimant if claim else ''
        alert.claimed_at = claim.claimed_at if claim else None
        alert.save(update_fields=['claimed_by', 'claimed_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0035_alert_center_defaults'),
    ]

    operations = [
        migrations.CreateModel(
            name='AlertClaim',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('claimant', models.CharField(max_length=64, verbose_name='认领人')),
                ('claimed_at', models.DateTimeField(auto_now_add=True, verbose_name='认领时间')),
                ('alert', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='claim_records', to='ops.alert', verbose_name='告警')),
            ],
            options={
                'verbose_name': '告警认领记录',
                'verbose_name_plural': '告警认领记录',
                'ordering': ['claimed_at', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='alertclaim',
            constraint=models.UniqueConstraint(fields=('alert', 'claimant'), name='uniq_ops_alert_claimant'),
        ),
        migrations.AddIndex(
            model_name='alertclaim',
            index=models.Index(fields=['alert', 'claimant'], name='ops_alrtclm_alrt_clm_idx'),
        ),
        migrations.RunPython(forwards, backwards),
    ]
