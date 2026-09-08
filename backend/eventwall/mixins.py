from .models import EventRecord
from .services import record_model_event, snapshot_instance


class EventWallModelViewSetMixin:
    event_module = ''
    event_category = 'resource_change'
    event_resource_type = ''
    event_resource_label = ''
    event_resource_name_fields = ()
    event_exclude_fields = ()
    event_tags = ()
    event_enabled = True

    def eventwall_should_record(self, action, instance=None):
        return bool(self.event_enabled and self.event_module and self.event_resource_type and self.event_resource_label)

    def eventwall_related_resources(self, instance):
        return []

    def eventwall_metadata(self, instance, action, before=None, after=None):
        return {}

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if response.status_code >= 400 or not self.eventwall_should_record('create'):
            return response
        instance_id = response.data.get('id')
        if instance_id:
            instance = self.get_queryset().get(pk=instance_id)
            after = snapshot_instance(instance, exclude_fields=self.event_exclude_fields)
            record_model_event(
                request=request,
                module=self.event_module,
                resource_type=self.event_resource_type,
                resource_label=self.event_resource_label,
                instance=instance,
                action='create',
                after=after,
                category=self.event_category,
                related_resources=self.eventwall_related_resources(instance),
                metadata=self.eventwall_metadata(instance, 'create', after=after),
                tags=list(self.event_tags),
                name_fields=self.event_resource_name_fields,
            )
        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        before = snapshot_instance(instance, exclude_fields=self.event_exclude_fields)
        response = super().update(request, *args, **kwargs)
        if response.status_code >= 400 or not self.eventwall_should_record('update', instance=instance):
            return response
        instance.refresh_from_db()
        after = snapshot_instance(instance, exclude_fields=self.event_exclude_fields)
        record_model_event(
            request=request,
            module=self.event_module,
            resource_type=self.event_resource_type,
            resource_label=self.event_resource_label,
            instance=instance,
            action='update',
            before=before,
            after=after,
            category=self.event_category,
            related_resources=self.eventwall_related_resources(instance),
            metadata=self.eventwall_metadata(instance, 'update', before=before, after=after),
            tags=list(self.event_tags),
            name_fields=self.event_resource_name_fields,
        )
        return response

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        before = snapshot_instance(instance, exclude_fields=self.event_exclude_fields)
        response = super().destroy(request, *args, **kwargs)
        if response.status_code >= 400 or not self.eventwall_should_record('delete', instance=instance):
            return response
        record_model_event(
            request=request,
            module=self.event_module,
            resource_type=self.event_resource_type,
            resource_label=self.event_resource_label,
            instance=instance,
            action='delete',
            before=before,
            category=self.event_category,
            result=EventRecord.RESULT_SUCCESS,
            severity=EventRecord.SEVERITY_WARNING,
            related_resources=self.eventwall_related_resources(instance),
            metadata=self.eventwall_metadata(instance, 'delete', before=before),
            tags=list(self.event_tags),
            name_fields=self.event_resource_name_fields,
        )
        return response

