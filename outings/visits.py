"""行ったことがある！／行ってみたい！, ratings and comments on trips,
子連れスポット and events (OutingsVisit)."""

from django.db.models import Avg, Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Event, FamilySpot, OutingsVisit, TouristSpot
from .visitor import get_visitor_id, set_visitor_cookie

Target = OutingsVisit.Target

DETAIL_URL = {
    Target.TRIP: "outings:tourist_spot_detail",
    Target.KIDS: "outings:spot_detail",
    Target.EVENT: "outings:event_detail",
}

# Events are one day, so the buttons read a little differently.
LABELS = {
    Target.EVENT: ("行った！", "行きたい！"),
}
DEFAULT_LABELS = ("行ったことがある！", "行ってみたい！")

MEMBER_RATINGS_NEEDED = 3  # members' average replaces our own おすすめ度 from here on


def target_object(target, pk):
    if target == Target.TRIP:
        from .tourist_views import tourist_spot_queryset
        return get_object_or_404(tourist_spot_queryset(), pk=pk)
    if target == Target.KIDS:
        return get_object_or_404(FamilySpot, pk=pk, status=FamilySpot.Status.PUBLISHED)
    if target == Target.EVENT:
        return get_object_or_404(Event, pk=pk, status=Event.Status.PUBLISHED)
    raise Http404


def my_visit(request, target, object_id, visitor_id):
    rows = OutingsVisit.objects.filter(target=target, object_id=object_id)
    if request.user.is_authenticated:
        mine = rows.filter(user=request.user).first()
        if mine:
            return mine
    return rows.filter(visitor_id=visitor_id).first()


def ratings(target, ids):
    """{object_id: (average, count)} from visible ratings."""
    rows = (
        OutingsVisit.objects.filter(target=target, object_id__in=list(ids), rating__isnull=False, is_hidden=False)
        .values("object_id").annotate(avg=Avg("rating"), n=Count("pk"))
    )
    return {row["object_id"]: (row["avg"], row["n"]) for row in rows}


def visit_context(request, target, obj, visitor_id):
    rows = OutingsVisit.objects.filter(target=target, object_id=obj.pk)
    counts = rows.aggregate(
        went=Count("pk", filter=Q(status=OutingsVisit.Status.WENT)),
        want=Count("pk", filter=Q(status=OutingsVisit.Status.WANT)),
        rated=Count("pk", filter=Q(rating__isnull=False, is_hidden=False)),
        avg=Avg("rating", filter=Q(is_hidden=False)),
    )
    reviews = list(
        rows.filter(status=OutingsVisit.Status.WENT, is_hidden=False)
        .filter(Q(rating__isnull=False) | ~Q(comment=""))
        .select_related("user")[:30]
    )
    went_label, want_label = LABELS.get(target, DEFAULT_LABELS)
    return {
        "target": target,
        "pk": obj.pk,
        "mine": my_visit(request, target, obj.pk, visitor_id),
        "went": counts["went"],
        "want": counts["want"],
        "rated": counts["rated"],
        "avg": round(counts["avg"], 1) if counts["avg"] else None,
        "reviews": reviews,
        "went_label": went_label,
        "want_label": want_label,
        "stars": range(1, 6),
    }


def stars_text(score):
    """★★★★☆ for a 1-5 score."""
    score = max(1, min(5, int(round(score))))
    return "★" * score + "☆" * (5 - score)


@require_POST
def save_visit(request, target, pk):
    if target not in Target.values:
        raise Http404
    obj = target_object(target, pk)
    visitor_id = get_visitor_id(request)
    visit = my_visit(request, target, obj.pk, visitor_id)
    action = request.POST.get("action", "")

    if action in OutingsVisit.Status.values:
        if visit and visit.status == action:
            # Pressed again: take it back (rating and comment go with it).
            visit.delete()
            visit = None
        else:
            visit = visit or OutingsVisit(target=target, object_id=obj.pk, visitor_id=visitor_id)
            visit.status = action
            if action == OutingsVisit.Status.WANT:
                visit.rating, visit.comment = None, ""
    elif action == "review":
        visit = visit or OutingsVisit(target=target, object_id=obj.pk, visitor_id=visitor_id)
        visit.status = OutingsVisit.Status.WENT
        try:
            rating = int(request.POST.get("rating", ""))
        except ValueError:
            rating = None
        visit.rating = rating if rating in range(1, 6) else visit.rating
        if request.user.is_authenticated:
            visit.comment = request.POST.get("comment", "").strip()[:500]
    else:
        raise Http404

    if visit is not None:
        if request.user.is_authenticated and visit.user_id is None:
            visit.user = request.user
        visit.save()

    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = reverse(DETAIL_URL[target], args=[obj.pk])
    response = redirect(next_url.split("#")[0] + "#visits")
    return set_visitor_cookie(request, response, visitor_id)


KIND_OF_TARGET = {Target.EVENT: "event", Target.TRIP: "trip", Target.KIDS: "kids"}


def mine_q(request, visitor_id):
    """Rows of this browser, or of the signed-in account on any device."""
    q = Q(visitor_id=visitor_id)
    if request.user.is_authenticated:
        q |= Q(user=request.user)
    return q


def went_keys(request, visitor_id):
    """{(kind, pk)} the visitor marked 行ったことがある, as find_views item keys."""
    rows = OutingsVisit.objects.filter(mine_q(request, visitor_id), status=OutingsVisit.Status.WENT)
    return {(KIND_OF_TARGET[t], pk) for t, pk in rows.values_list("target", "object_id")}


def hidden_keys(request, visitor_id, preference):
    """Places to leave out of HOME, さがす and 一覧 (マイページ setting)."""
    if preference is None or not preference.hide_went:
        return set()
    return went_keys(request, visitor_id)
