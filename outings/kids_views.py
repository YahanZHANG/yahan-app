"""子連れスポット: places families can go any day.

Filters are plain links like the search page, so every state has its own URL.
"""

from django.shortcuts import get_object_or_404, render

from .event_views import querystring
from .models import FamilySpot
from .regions import REGION_NAMES_JA


KIND_EMOJI = {
    FamilySpot.Kind.PARK: "🛝",
    FamilySpot.Kind.ANIMALS: "🦒",
    FamilySpot.Kind.MUSEUM: "🦖",
    FamilySpot.Kind.INDOOR: "🏠",
    FamilySpot.Kind.NATURE: "🌲",
    FamilySpot.Kind.OTHER: "🎈",
}

# (key, label, icon) of the yes/no filters.
TOGGLES = [
    ("rainy", "雨の日OK", "bi-umbrella"),
    ("free", "入場無料", "bi-cash-coin"),
    ("sunday", "日曜もOK", "bi-calendar-check"),
]


def published_spots():
    return FamilySpot.objects.filter(status=FamilySpot.Status.PUBLISHED)


def decorate(spot):
    """Emoji and short badges shown on cards and the detail page."""
    spot.emoji = KIND_EMOJI.get(spot.kind, "🎈")
    badges = []
    if spot.rainy_ok:
        badges.append(("雨の日OK", "family"))
    if spot.price == FamilySpot.Price.FREE:
        badges.append(("無料", "free"))
    elif spot.price == FamilySpot.Price.PARTLY:
        badges.append(("入場無料", "free"))
    if spot.open_sunday:
        badges.append(("日曜OK", "ok"))
    if spot.stroller_ok:
        badges.append(("ベビーカーOK", "ok"))
    spot.badges = badges
    return spot


def spot_list(request):
    get = request.GET
    kind = get.get("kind", "")
    if kind not in FamilySpot.Kind.values:
        kind = ""
    canton = get.get("canton", "")
    flags = {key: get.get(key) == "1" for key, _, _ in TOGGLES}

    spots = published_spots()
    if kind:
        spots = spots.filter(kind=kind)
    if canton:
        spots = spots.filter(canton=canton)
    if flags["rainy"]:
        spots = spots.filter(rainy_ok=True)
    if flags["free"]:
        spots = spots.exclude(price=FamilySpot.Price.PAID)
    if flags["sunday"]:
        spots = spots.filter(open_sunday=True)
    spots = [decorate(spot) for spot in spots]

    params = {"kind": kind, "canton": canton, **{key: "1" if on else "" for key, on in flags.items()}}

    def link(**changes):
        return querystring(params, **changes)

    used_cantons = sorted(set(published_spots().exclude(canton="").values_list("canton", flat=True)))
    chips = {
        "toggles": [
            {"label": label, "icon": icon, "active": flags[key], "qs": link(**{key: "" if flags[key] else "1"})}
            for key, label, icon in TOGGLES
        ],
        "kinds": [{"label": "すべて", "emoji": "✨", "active": not kind, "qs": link(kind="")}] + [
            {"label": label, "emoji": KIND_EMOJI[value], "active": value == kind, "qs": link(kind="" if value == kind else value)}
            for value, label in FamilySpot.Kind.choices
            if value != FamilySpot.Kind.OTHER
        ],
        "cantons": [{"label": "すべて", "active": not canton, "qs": link(canton="")}] + [
            {"label": REGION_NAMES_JA.get(code, code), "active": code == canton, "qs": link(canton="" if code == canton else code)}
            for code in used_cantons
        ],
    }
    return render(request, "outings/kids_list.html", {
        "spots": spots,
        "chips": chips,
        "filtered": bool(kind or canton or any(flags.values())),
        "clear_qs": link(kind="", canton="", rainy="", free="", sunday=""),
    })


def spot_detail(request, pk):
    spot = decorate(get_object_or_404(published_spots(), pk=pk))
    others = [decorate(s) for s in published_spots().exclude(pk=spot.pk).filter(kind=spot.kind)[:3]]
    return render(request, "outings/kids_detail.html", {"spot": spot, "others": others})
