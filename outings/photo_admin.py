"""Staff only: replace or remove the photo of a trip, 子連れスポット or event
right on the normal pages (detail pages and list cards).

A removed photo stays removed: the automatic Wikimedia search and the
Eventfrog photo step skip it."""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Event, FamilySpot, TouristSpot

TARGETS = ("trip", "kids", "event")
DETAIL_URL = {"trip": "outings:tourist_spot_detail", "kids": "outings:spot_detail", "event": "outings:event_detail"}
FOLDER = "yapp/outings/places"


def get_target(target, pk):
    model = {"trip": TouristSpot, "kids": FamilySpot, "event": Event}[target]
    return get_object_or_404(model, pk=pk)


def current_url(target, obj):
    if target == "trip":
        return ((obj.details or {}).get("approved_image") or {}).get("url", "")
    return obj.image_url


def set_photo(target, obj, url, credit, kind):
    if target == "trip":
        details = dict(obj.details or {})
        details["approved_image"] = {
            "url": url, "credit": credit, "image_type": kind, "reviewed": True, "selection_method": "manual",
        }
        details["commons_search_checked"] = True
        details.pop("photo_removed", None)
        obj.details = details
        obj.save(update_fields=["details", "updated_at"])
        return
    obj.image_url = url
    obj.image_credit = credit
    obj.image_search_done = True
    obj.image_removed = False
    obj.save(update_fields=["image_url", "image_credit", "image_search_done", "image_removed"])


def remove_photo(target, obj):
    if target == "trip":
        details = dict(obj.details or {})
        details.pop("approved_image", None)
        details["commons_search_checked"] = True  # the auto search won't add one again
        details["photo_removed"] = True
        obj.details = details
        obj.save(update_fields=["details", "updated_at"])
        return
    obj.image_url = ""
    obj.image_credit = ""
    obj.image_search_done = True
    obj.image_removed = True  # the automatic photo steps won't add one back
    obj.save(update_fields=["image_url", "image_credit", "image_search_done", "image_removed"])


def _delete_old(url):
    if url and "res.cloudinary.com/" in url:
        from .management.commands.cleanup_outings import delete_photos
        delete_photos([url], lambda message: None)


@staff_member_required
@require_POST
def staff_photo(request, target, pk):
    if target not in TARGETS:
        target = "kids"
    obj = get_target(target, pk)
    old = current_url(target, obj)
    action = request.POST.get("action")
    credit = request.POST.get("credit", "").strip()[:200]
    try:
        if action == "remove":
            remove_photo(target, obj)
            _delete_old(old)
            messages.success(request, "写真を削除しました。")
        elif request.FILES.get("photo"):
            from .services.user_event_cloudinary import upload_user_event_photo
            from .services.user_event_images import process_user_event_image
            processed = process_user_event_image(request.FILES["photo"], max_size=1600, quality=80)
            url = upload_user_event_photo(processed, folder=FOLDER, filename="photo.webp")
            set_photo(target, obj, url, credit, "upload")
            _delete_old(old)
            messages.success(request, "写真を差し替えました。")
        elif request.POST.get("url", "").strip().startswith("https://"):
            set_photo(target, obj, request.POST["url"].strip()[:1000], credit, "link")
            if old != request.POST["url"].strip():
                _delete_old(old)
            messages.success(request, "写真を差し替えました。")
        else:
            messages.error(request, "写真のファイルか、https で始まる写真のURLを入れてください。")
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))

    back = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        back = reverse(DETAIL_URL[target], args=[obj.pk])
    return redirect(back)
