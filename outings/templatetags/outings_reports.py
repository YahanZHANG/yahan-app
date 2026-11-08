from django import template

from outings.models import OutingsReport

register = template.Library()


@register.simple_tag
def pending_photos(target, pk):
    """Photos visitors sent for this place, still waiting for an admin."""
    return OutingsReport.objects.filter(target=target, object_id=pk, is_done=False).exclude(photo_url="").select_related("user")[:6]
