"""「地図で見る」 on the lists: the same list view answers ?map=1 with the
places of every result (not only the current page) as JSON."""

from django.http import JsonResponse
from django.urls import reverse

MAX_POINTS = 800


def wants_map(request):
    return request.GET.get("map") == "1"


def _point(title, url, lat, lon, emoji, sub=""):
    if lat is None or lon is None:
        return None
    return {"title": title, "url": url, "lat": round(float(lat), 5), "lon": round(float(lon), 5),
            "emoji": emoji or "📍", "sub": sub}


def event_point(event):
    location = event.location
    if location is None:
        return None
    return _point(event.title, reverse("outings:event_detail", args=[event.pk]),
                  location.latitude, location.longitude, getattr(event, "display_emoji", "🎪"), location.city)


def trip_point(spot):
    from .sunny import SPOT_TYPE_EMOJI
    return _point((spot.title_ja or spot.title_original).split("｜")[0],
                  reverse("outings:tourist_spot_detail", args=[spot.pk]),
                  spot.latitude, spot.longitude, SPOT_TYPE_EMOJI.get(spot.spot_type, "📍"), spot.get_spot_type_display())


def kids_point(spot):
    return _point(spot.title, reverse("outings:spot_detail", args=[spot.pk]),
                  spot.latitude, spot.longitude, spot.emoji, spot.town)


def map_response(points, total=None):
    """`points` may hold None for results without a known place; they count in total."""
    total = len(points) if total is None else total
    points = [p for p in points if p]
    return JsonResponse({"points": points[:MAX_POINTS], "total": total,
                         "shown": min(len(points), MAX_POINTS)})
