from .models import ActivityEvent

def record_activity(
        actor,
        action,
        target_type,
        target_id,
        details=None,
):
    return ActivityEvent.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        details=details or {},
    )