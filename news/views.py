from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings as django_settings
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils.http import (
    url_has_allowed_host_and_scheme,
)

from .forms import NewsSettingsForm
from .models import (
    Article,
    Favorite,
    NewsDigest,
    NewsPreference,
    Topic,
)


def _get_preference(user):
    preference, _ = (
        NewsPreference.objects.get_or_create(
            user=user
        )
    )

    return preference


def _article_queryset(
    user,
    preference,
):
    hidden_topics = (
        preference.hidden_topics.all()
    )

    queryset = (
        Article.objects
        .select_related(
            "source"
        )
        .prefetch_related(
            "topics"
        )
        .annotate(
            is_favorite=Exists(
                Favorite.objects.filter(
                    user=user,
                    article=OuterRef("pk"),
                )
            )
        )
    )

    if hidden_topics.exists():

        visible_topics = (
            Topic.objects
            .filter(
                is_active=True
            )
            .exclude(
                id__in=(
                    hidden_topics
                    .values_list(
                        "id",
                        flat=True,
                    )
                )
            )
        )

        queryset = (
            queryset
            .filter(
                Q(
                    topics__in=visible_topics
                )
                |
                Q(
                    topics__isnull=True
                )
            )
            .distinct()
        )

    return queryset


def _safe_redirect(
    request,
    default="news:home",
):
    next_url = request.POST.get(
        "next"
    )

    if (
        next_url
        and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={
                request.get_host()
            },
            require_https=(
                request.is_secure()
            ),
        )
    ):
        return redirect(
            next_url
        )

    return redirect(
        default
    )


@login_required
def home(request):
    preference = _get_preference(
        request.user
    )

    articles = (
        _article_queryset(
            request.user,
            preference,
        )
        .order_by(
            "-published_at"
        )[:100]
    )

    favorite_count = (
        Favorite.objects
        .filter(
            user=request.user
        )
        .count()
    )

    latest_digest = (
        NewsDigest.objects
        .order_by(
            "-generated_at"
        )
        .first()
    )

    return render(
        request,
        "news/home.html",
        {
            "articles": articles,
            "preference": preference,
            "favorite_count": favorite_count,
            "latest_digest": latest_digest,
        },
    )

@login_required
def topic_list(request):
    preference = _get_preference(
        request.user
    )

    hidden_ids = (
        preference
        .hidden_topics
        .values_list(
            "id",
            flat=True,
        )
    )

    topics = (
        Topic.objects
        .filter(
            is_active=True
        )
        .exclude(
            id__in=hidden_ids
        )
    )

    return render(
        request,
        "news/topic_list.html",
        {
            "topics": topics,
            "preference": preference,
        },
    )


@login_required
def topic_detail(
    request,
    slug,
):
    preference = _get_preference(
        request.user
    )

    topic = get_object_or_404(
        Topic,
        slug=slug,
        is_active=True,
    )

    articles = (
        _article_queryset(
            request.user,
            preference,
        )
        .filter(
            topics=topic
        )[:50]
    )

    return render(
        request,
        "news/topic_detail.html",
        {
            "topic": topic,
            "articles": articles,
            "preference": preference,
        },
    )


@login_required
def favorites(request):
    preference = _get_preference(
        request.user
    )

    articles = (
        Article.objects
        .filter(
            favorites__user=(
                request.user
            )
        )
        .select_related(
            "source"
        )
        .prefetch_related(
            "topics"
        )
        .annotate(
            is_favorite=Exists(
                Favorite.objects.filter(
                    user=request.user,
                    article=OuterRef(
                        "pk"
                    ),
                )
            )
        )
        .order_by(
            "-favorites__created_at"
        )
    )

    favorite_count = (
        Favorite.objects
        .filter(
            user=request.user
        )
        .count()
    )

    return render(
        request,
        "news/favorites.html",
        {
            "articles": articles,
            "preference": preference,
            "favorite_count": (
                favorite_count
            ),
        },
    )


@login_required
def toggle_favorite(
    request,
    article_id,
):
    if request.method != "POST":
        return redirect(
            "news:home"
        )

    article = get_object_or_404(
        Article,
        id=article_id,
    )

    favorite = (
        Favorite.objects
        .filter(
            user=request.user,
            article=article,
        )
        .first()
    )

    if favorite:

        favorite.delete()

        messages.success(
            request,
            "お気に入りから削除しました。"
        )

        return _safe_redirect(
            request
        )

    count = (
        Favorite.objects
        .filter(
            user=request.user
        )
        .count()
    )

    if count >= 10:

        messages.error(
            request,
            "お気に入りは10件までです。"
        )

        return _safe_redirect(
            request
        )

    Favorite.objects.create(
        user=request.user,
        article=article,
    )

    messages.success(
        request,
        "お気に入りに保存しました。"
    )

    return _safe_redirect(
        request
    )


@login_required
def settings_view(request):
    preference = _get_preference(
        request.user
    )

    if request.method == "POST":

        form = NewsSettingsForm(
            request.POST,
            instance=preference,
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                "設定を保存しました。"
            )

            return redirect(
                "news:settings"
            )

    else:

        form = NewsSettingsForm(
            instance=preference
        )

    return render(
        request,
        "news/settings.html",
        {
            "form": form,
            "preference": preference,
            "vapid_public_key": django_settings.VAPID_PUBLIC_KEY,
        },
    )

@login_required
def digest_list(request):

    digests = (
        NewsDigest.objects
        .order_by(
            "-digest_date",
            "-generated_at",
        )
    )

    return render(
        request,
        "news/digest_list.html",
        {
            "digests": digests,
        },
    )