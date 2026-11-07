"""お気に入り: ♡ お気に入り, ✨ 行ってみたい and 🙌 行った on one page,
for the visitor alone or for the whole family."""

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from . import family
from . import profile as visitor_profile
from .models import EventHeart, OutingsVisit, TouristSpotHeart
from .visitor import get_visitor_id, set_visitor_cookie
from .visits import KIND_OF_TARGET

TABS = [("heart", "♡", "お気に入り"), ("want", "✨", "行ってみたい"), ("went", "🙌", "行った")]


def _owner_q(request, visitor_id, users):
    q = Q(visitor_id=visitor_id)
    if users:
        q |= Q(user__in=users)
    elif request.user.is_authenticated:
        q |= Q(user=request.user)
    return q


def _collect_keys(request, visitor_id, users):
    """{tab: {(kind, pk): {"users": {user_id}, "at": datetime, "rating": n}}}"""
    q = _owner_q(request, visitor_id, users)
    found = {key: {} for key, *_ in TABS}

    def add(tab, key, user_id, at, rating=None):
        row = found[tab].setdefault(key, {"users": set(), "at": at, "ratings": []})
        if user_id:
            row["users"].add(user_id)
        elif request.user.is_authenticated:
            row["users"].add(request.user.pk)  # this browser, before signing in
        row["at"] = max(row["at"], at)
        if rating:
            row["ratings"].append((user_id, rating))

    for event_id, user_id, at in EventHeart.objects.filter(q).values_list("event_id", "user_id", "created_at"):
        add("heart", ("event", event_id), user_id, at)
    for spot_id, user_id, at in TouristSpotHeart.objects.filter(q).values_list("spot_id", "user_id", "created_at"):
        add("heart", ("trip", spot_id), user_id, at)
    for target, pk, status, user_id, at, rating in OutingsVisit.objects.filter(q).values_list(
        "target", "object_id", "status", "user_id", "updated_at", "rating",
    ):
        add(status, (KIND_OF_TARGET[target], pk), user_id, at, rating)
    return found


def saved(request):
    from . import find_views
    visitor_id = get_visitor_id(request)
    preference = visitor_profile.get_profile(visitor_id)
    tab = request.GET.get("tab", "heart")
    if tab not in dict((k, l) for k, _, l in TABS):
        tab = "heart"
    people = family.members(request.user)
    who = "family" if request.GET.get("who") == "family" and len(people) > 1 else "me"
    users = people if who == "family" else []

    found = _collect_keys(request, visitor_id, users)
    now = timezone.now()
    every = find_views.collect(
        find_views.base_filters(False, when="any", sort="recommended"), now, [], None,
    )
    by_key = {(i["kind"], i["pk"]): i for i in every["event"] + every["trip"] + every["kids"]}

    counts = {key: sum(1 for k in found[key] if k in by_key) for key, *_ in TABS}
    names = {u.pk: u for u in people}
    items = []
    for key, row in sorted(found[tab].items(), key=lambda kv: kv[1]["at"], reverse=True):
        item = by_key.get(key)
        if item is None:
            continue  # ended event or unpublished place
        if who == "family":
            item["by"] = [names[pk] for pk in names if pk in row["users"]]
            item["by_ratings"] = [(names[pk], r) for pk, r in row["ratings"] if pk in names]
        else:
            item["my_rating"] = row["ratings"][0][1] if row["ratings"] else None
        items.append(item)
    find_views.score_items(items, [], {}, preference)

    response = render(request, "outings/saved.html", {
        "tabs": [{"key": k, "icon": i, "label": l, "count": counts[k], "active": k == tab} for k, i, l in TABS],
        "tab": tab,
        "who": who,
        "has_family": len(people) > 1,
        "items": items,
    })
    return set_visitor_cookie(request, response, visitor_id)


@login_required
def family_page(request):
    from washoku.models import HouseholdInvite
    mine = family.membership(request.user)
    return render(request, "outings/family.html", {
        "membership": mine,
        "members": family.members(request.user) or [request.user],
        "received_invites": HouseholdInvite.objects.filter(invited_user=request.user, status="pending").select_related("invited_by"),
        "sent_invites": (
            HouseholdInvite.objects.filter(household=mine.household, status="pending").select_related("invited_user")
            if mine else []
        ),
    })
