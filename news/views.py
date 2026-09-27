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

def _get_public_settings(request):
    """
    未ログインユーザーのニュース設定を
    Django session から取得する。
    """

    settings = request.session.get(
        "news_public_settings",
        {}
    )

    return {
        "display_language": settings.get(
            "display_language",
            "ja",
        ),
        "font_size": settings.get(
            "font_size",
            "medium",
        ),
        "enabled_topic_ids": settings.get(
            "enabled_topic_ids",
            None,
        ),
    }

def _apply_public_topic_settings(
    queryset,
    public_settings,
):
    """
    未ログインユーザーがsessionで選択した
    ニューステーマを記事一覧に反映する。
    """

    enabled_topic_ids = (
        public_settings.get(
            "enabled_topic_ids"
        )
    )

    # まだ設定を保存したことがない場合は
    # 全テーマを表示する。
    if enabled_topic_ids is None:
        return queryset

    # 全テーマをOFFにした場合は、
    # テーマ未設定の記事だけ表示する。
    if not enabled_topic_ids:
        return (
            queryset
            .filter(
                topics__isnull=True
            )
            .distinct()
        )

    return (
        queryset
        .filter(
            Q(
                topics__id__in=(
                    enabled_topic_ids
                )
            )
            |
            Q(
                topics__isnull=True
            )
        )
        .distinct()
    )

def _article_queryset(
    user=None,
    preference=None,
):
    queryset = (
        Article.objects
        .select_related(
            "source"
        )
        .prefetch_related(
            "topics"
        )
    )

    if (
        user is not None
        and user.is_authenticated
    ):
        queryset = (
            queryset
            .annotate(
                is_favorite=Exists(
                    Favorite.objects.filter(
                        user=user,
                        article=OuterRef("pk"),
                    )
                )
            )
        )

    if preference is not None:

        hidden_topics = (
            preference.hidden_topics.all()
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


def home(request):

    preference = None
    public_settings = None
    favorite_count = 0

    if request.user.is_authenticated:

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

    else:

        public_settings = (
            _get_public_settings(
                request
            )
        )

        articles = (
            _article_queryset()
        )

        articles = (
            _apply_public_topic_settings(
                articles,
                public_settings,
            )
        )

        articles = (
            articles
            .order_by(
                "-published_at"
            )[:100]
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
            "public_settings": public_settings,
            "favorite_count": favorite_count,
            "latest_digest": latest_digest,
        },
    )


def topic_list(request):

    preference = None
    public_settings = None

    topics = (
        Topic.objects
        .filter(
            is_active=True
        )
    )

    if request.user.is_authenticated:

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
            topics
            .exclude(
                id__in=hidden_ids
            )
        )

    else:

        public_settings = (
            _get_public_settings(
                request
            )
        )

        enabled_topic_ids = (
            public_settings.get(
                "enabled_topic_ids"
            )
        )

        if enabled_topic_ids is not None:

            topics = (
                topics
                .filter(
                    id__in=enabled_topic_ids
                )
            )

    return render(
        request,
        "news/topic_list.html",
        {
            "topics": topics,
            "preference": preference,
            "public_settings": public_settings,
        },
    )


def topic_detail(
    request,
    slug,
):
    preference = None
    public_settings = None

    topic = get_object_or_404(
        Topic,
        slug=slug,
        is_active=True,
    )

    if request.user.is_authenticated:

        preference = _get_preference(
            request.user
        )

        articles = (
            _article_queryset(
                request.user,
                preference,
            )
            .filter(
                topics=topic
            )
            .order_by(
                "-published_at"
            )[:50]
        )

    else:

        public_settings = (
            _get_public_settings(
                request
            )
        )

        articles = (
            _article_queryset()
            .filter(
                topics=topic
            )
            .order_by(
                "-published_at"
            )[:50]
        )

    return render(
        request,
        "news/topic_detail.html",
        {
            "topic": topic,
            "articles": articles,
            "preference": preference,
            "public_settings": public_settings,
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


def settings_view(request):

    # =====================================================
    # Logged-in user
    # =====================================================

    if request.user.is_authenticated:

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
            },
        )


    # =====================================================
    # Public / anonymous user
    # =====================================================

    preference = None

    active_topics = (
        Topic.objects
        .filter(
            is_active=True
        )
    )

    default_topic_ids = list(
        active_topics.values_list(
            "id",
            flat=True,
        )
    )


    if request.method == "POST":

        form = NewsSettingsForm(
            request.POST
        )

        if form.is_valid():

            enabled_topics = (
                form.cleaned_data[
                    "enabled_topics"
                ]
            )

            request.session[
                "news_public_settings"
            ] = {
                "display_language": (
                    form.cleaned_data[
                        "display_language"
                    ]
                ),
                "font_size": (
                    form.cleaned_data[
                        "font_size"
                    ]
                ),
                "enabled_topic_ids": list(
                    enabled_topics.values_list(
                        "id",
                        flat=True,
                    )
                ),
            }

            request.session.modified = True

            messages.success(
                request,
                "設定を保存しました。"
            )

            return redirect(
                "news:settings"
            )

    else:

        public_settings = (
            request.session.get(
                "news_public_settings",
                {}
            )
        )

        form = NewsSettingsForm(
            initial={
                "display_language": (
                    public_settings.get(
                        "display_language",
                        "ja",
                    )
                ),
                "font_size": (
                    public_settings.get(
                        "font_size",
                        "medium",
                    )
                ),
                "enabled_topics": (
                    public_settings.get(
                        "enabled_topic_ids",
                        default_topic_ids,
                    )
                ),
            }
        )


    return render(
        request,
        "news/settings.html",
        {
            "form": form,
            "preference": preference,
        },
    )


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