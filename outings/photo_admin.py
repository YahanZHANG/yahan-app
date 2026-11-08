"""Staff only: replace or remove the photo of a trip, 子連れスポット or event
right on the normal pages (detail pages and list cards).

A removed photo stays removed: the automatic Wikimedia search and the
Eventfrog photo step skip it."""

import re
from urllib.parse import quote, unquote, urlparse

import requests
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


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
COMMONS_FILE = re.compile(r"(?:File|Datei|Fichier|Image|ファイル):([^?#/]+)", re.I)


def commons_file(url):
    """'Alpamare.jpg' from a Commons or Wikipedia file page link, else ''."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if not (host.endswith("wikimedia.org") or host.endswith("wikipedia.org")) or host == "upload.wikimedia.org":
        return ""
    found = COMMONS_FILE.search(unquote(parsed.path + "#" + parsed.fragment + "?" + parsed.query))
    return found.group(1).replace("_", " ").strip() if found else ""


def commons_photo(name):
    """{url, source_url, credit, license_url} for a Commons file. Falls back
    to Special:FilePath (always shows the picture) when the API can't be read."""
    page = "https://commons.wikimedia.org/wiki/File:" + quote(name.replace(" ", "_"))
    photo = {
        "url": "https://commons.wikimedia.org/wiki/Special:FilePath/" + quote(name.replace(" ", "_")) + "?width=1600",
        "source_url": page, "credit": "Wikimedia Commons", "license_url": "",
    }
    try:
        from .management.commands.find_tourist_images import USER_AGENT, clean_text
        response = requests.get(COMMONS_API, params={
            "action": "query", "titles": "File:" + name, "prop": "imageinfo",
            "iiprop": "url|extmetadata", "iiurlwidth": 1600, "format": "json", "formatversion": 2,
        }, headers={"User-Agent": USER_AGENT}, timeout=15)
        response.raise_for_status()
        info = ((response.json().get("query", {}).get("pages") or [{}])[0].get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        if (info.get("thumburl") or "").startswith("https://"):
            photo["url"] = info["thumburl"]
        author = clean_text(meta.get("Artist"))
        license_name = clean_text(meta.get("LicenseShortName"))
        if author or license_name:
            photo["credit"] = " / ".join(x for x in (author, license_name) if x)[:200]
        photo["license_url"] = clean_text(meta.get("LicenseUrl"))
    except (requests.RequestException, ValueError, KeyError, IndexError, ImportError):
        pass
    return photo


def get_target(target, pk):
    model = {"trip": TouristSpot, "kids": FamilySpot, "event": Event}[target]
    return get_object_or_404(model, pk=pk)


def current_url(target, obj):
    if target == "trip":
        return ((obj.details or {}).get("approved_image") or {}).get("url", "")
    return obj.image_url


def set_photo(target, obj, url, credit, kind, source_url="", license_url=""):
    if target == "trip":
        details = dict(obj.details or {})
        details["approved_image"] = {
            "url": url, "credit": credit, "image_type": kind, "reviewed": True, "selection_method": "manual",
            "source_url": source_url, "license_url": license_url,
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
            link = request.POST["url"].strip()[:1000]
            name = commons_file(link)
            if name:
                # A Wikimedia file page, not the picture itself: find the picture and its credit.
                photo = commons_photo(name)
                set_photo(target, obj, photo["url"], credit or photo["credit"], "wikimedia",
                          photo["source_url"], photo["license_url"])
            else:
                set_photo(target, obj, link, credit, "link")
            if old != link:
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
