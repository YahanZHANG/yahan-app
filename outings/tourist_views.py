
from datetime import date

from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Coalesce

from django.http import (
    HttpResponseRedirect,
    JsonResponse,
)

from django.shortcuts import (
    get_object_or_404,
    render,
)

from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import (
    TouristSpot,
    TouristSpotHeart,
)

from .visitor import (
    get_visitor_id,
    set_visitor_cookie,
)


# =========================================================
# Spot categories
# =========================================================

SPOT_CATEGORIES = {
    "all": "すべて",
    "attractions": "観光・体験",
    "tours": "散策・ハイキング",
    "destinations": "旅行先・地域",
    "offers": "体験・ツアー",
}


# =========================================================
# Public tourist spots
# =========================================================

def tourist_spot_queryset():

    """
    Public tourism records.

    Exclude expired offers.
    Keep other spot types available year-round.
    """

    today = date.today()

    spots = TouristSpot.objects.filter(
        status=TouristSpot.Status.PUBLISHED
    )

    return spots.exclude(
        Q(
            spot_type=TouristSpot.SpotType.OFFER
        )
        & Q(
            details__validThrough__lt=today.isoformat()
        )
        & ~Q(
            details__validThrough=""
        )
    )


# =========================================================
# Tourist spot list
# =========================================================

def tourist_spot_list(request):

    # =====================================================
    # Request parameters
    # =====================================================

    category = request.GET.get(
        "category",
        "all",
    )

    if category not in SPOT_CATEGORIES:
        category = "all"

    query = (
        request.GET.get("q", "")
        .strip()[:100]
    )

    show_all = (
        request.GET.get("all") == "1"
    )

    sort = request.GET.get(
        "sort",
        "recommended",
    )

    if sort not in (
        "recommended",
        "updated",
        "name",
    ):
        sort = "recommended"

    # =====================================================
    # Base queryset
    # =====================================================

    spots = tourist_spot_queryset()

    # =====================================================
    # Category
    # =====================================================

    if category != "all":
        spots = spots.filter(
            spot_type=category
        )

    # =====================================================
    # Search / quality filter
    # =====================================================

    if query:

        spots = spots.filter(
            Q(title_original__icontains=query)
            | Q(title_ja__icontains=query)
            | Q(summary_original__icontains=query)
            | Q(summary_ja__icontains=query)
        )

    elif not show_all:

        spots = spots.filter(
            ai_quality_score__gte=50
        )

    # =====================================================
    # Sorting
    # =====================================================

    spots = spots.annotate(
        sort_score=Coalesce(
            "ai_quality_score",
            Value(-1),
        )
    )

    if sort == "updated":

        spots = spots.order_by(
            "-updated_at",
            "pk",
        )

    elif sort == "name":

        spots = spots.order_by(
            "title_original",
            "pk",
        )

    else:

        spots = spots.order_by(
            "-sort_score",
            "title_original",
            "pk",
        )

    # =====================================================
    # Pagination
    # =====================================================

    paginator = Paginator(
        spots,
        24,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    # =====================================================
    # Tourist spot hearts
    # =====================================================

    visitor_id = get_visitor_id(request)

    visible_spots = list(
        page_obj.object_list
    )

    visible_spot_ids = [
        spot.pk
        for spot in visible_spots
    ]

    hearted_ids = set(
        TouristSpotHeart.objects.filter(
            visitor_id=visitor_id,
            spot_id__in=visible_spot_ids,
        ).values_list(
            "spot_id",
            flat=True,
        )
    )

    for spot in visible_spots:

        spot.is_hearted = (
            spot.pk in hearted_ids
        )

    # Make sure the template uses
    # the objects with is_hearted assigned.
    page_obj.object_list = visible_spots

    # =====================================================
    # Render
    # =====================================================

    response = render(
        request,
        "outings/tourist_spot_list.html",
        {
            "page_obj": page_obj,
            "categories": SPOT_CATEGORIES,
            "selected_category": category,
            "query": query,
            "show_all": show_all,
            "sort": sort,
            "result_count": paginator.count,
        },
    )

    return set_visitor_cookie(
        request,
        response,
        visitor_id,
    )


# =========================================================
# Tourist spot detail
# =========================================================

def tourist_spot_detail(request, pk):

    spot = get_object_or_404(
        tourist_spot_queryset(),
        pk=pk,
    )

    details = spot.details or {}

    warnings = None

    if (
        spot.spot_type
        == TouristSpot.SpotType.TOUR
    ):

        mobility = details.get(
            "switzerlandMobility",
            {},
        )

        if isinstance(mobility, dict):
            warnings = mobility.get(
                "warnings"
            )

    price = None

    if (
        spot.spot_type
        == TouristSpot.SpotType.OFFER
    ):

        price = details.get(
            "priceSpecification",
            {},
        )

    # =====================================================
    # Heart status
    # =====================================================

    visitor_id = get_visitor_id(request)

    is_hearted = (
        TouristSpotHeart.objects.filter(
            spot=spot,
            visitor_id=visitor_id,
        ).exists()
    )

    # =====================================================
    # Render
    # =====================================================

    response = render(
        request,
        "outings/tourist_spot_detail.html",
        {
            "spot": spot,
            "details": details,
            "warnings": warnings,
            "price": price,
            "category_label": (
                SPOT_CATEGORIES.get(
                    spot.spot_type,
                    "観光情報",
                )
            ),
            "is_hearted": is_hearted,
        },
    )

    return set_visitor_cookie(
        request,
        response,
        visitor_id,
    )


# =========================================================
# Toggle tourist heart
# =========================================================

@require_POST
def toggle_tourist_heart(request, pk):

    spot = get_object_or_404(
        tourist_spot_queryset(),
        pk=pk,
    )

    visitor_id = get_visitor_id(request)

    heart, created = (
        TouristSpotHeart.objects.get_or_create(
            spot=spot,
            visitor_id=visitor_id,
        )
    )

    if not created:
        heart.delete()

    hearted = created

    # =====================================================
    # AJAX request from HOME
    # =====================================================

    if (
        request.headers.get(
            "X-Requested-With"
        ) == "XMLHttpRequest"
    ):

        response = JsonResponse({
            "hearted": hearted,
        })

        return set_visitor_cookie(
            request,
            response,
            visitor_id,
        )

    # =====================================================
    # Normal form POST
    # =====================================================

    default_url = reverse(
        "outings:tourist_spot_detail",
        args=[spot.pk],
    )

    next_url = (
        request.POST.get("next", "")
        .strip()
    )

    if (
        next_url
        and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={
                request.get_host()
            },
            require_https=request.is_secure(),
        )
    ):

        redirect_url = next_url

    else:

        redirect_url = default_url

    response = HttpResponseRedirect(
        redirect_url
    )

    return set_visitor_cookie(
        request,
        response,
        visitor_id,
    )
