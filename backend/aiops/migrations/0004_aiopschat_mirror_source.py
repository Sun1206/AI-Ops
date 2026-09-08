from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aiops', '0003_platform_builtin_labels'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiopschatsession',
            name='mirror_source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mirrored_sessions', to='aiops.aiopschatsession', verbose_name='镜像来源'),
        ),
        migrations.AddField(
            model_name='aiopschatmessage',
            name='mirror_source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mirrored_messages', to='aiops.aiopschatmessage', verbose_name='镜像来源'),
        ),
        migrations.AddField(
            model_name='aiopspendingaction',
            name='mirror_source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mirrored_actions', to='aiops.aiopspendingaction', verbose_name='镜像来源'),
        ),
        migrations.AddConstraint(
            model_name='aiopschatsession',
            constraint=models.UniqueConstraint(fields=('user', 'mirror_source'), name='aiops_session_user_mirror_source_uniq'),
        ),
        migrations.AddConstraint(
            model_name='aiopschatmessage',
            constraint=models.UniqueConstraint(fields=('session', 'mirror_source'), name='aiops_message_session_mirror_source_uniq'),
        ),
        migrations.AddConstraint(
            model_name='aiopspendingaction',
            constraint=models.UniqueConstraint(fields=('session', 'mirror_source'), name='aiops_action_session_mirror_source_uniq'),
        ),
    ]
