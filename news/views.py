from django.contrib import messages
from django.utils import timezone
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

from .forms import (
    NewsFeedbackForm,
    NewsSettingsForm,
)

from .models import (
    Article,
    Favorite,
    NewsDigest,
    NewsPreference,
    NewsSource,
    Region,
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
        {},
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

        "enabled_region_ids": settings.get(
            "enabled_region_ids",
            None,
        ),

        "enabled_source_ids": settings.get(
            "enabled_source_ids",
            None,
        ),
    }

def _apply_public_news_settings(
    queryset,
    public_settings,
):

    """
    未ログインユーザーがsessionで選択した
    テーマ・地域・ニュースソースを
    記事一覧に反映する。
    """

    enabled_topic_ids = public_settings.get(
        "enabled_topic_ids"
    )

    enabled_region_ids = public_settings.get(
        "enabled_region_ids"
    )

    enabled_source_ids = public_settings.get(
        "enabled_source_ids"
    )


    # =====================================================
    # Topics
    # =====================================================

    if enabled_topic_ids is not None:

        if enabled_topic_ids:

            queryset = (
                queryset
                .filter(
                    Q(
                        topics__id__in=enabled_topic_ids
                    )
                    |
                    Q(
                        topics__isnull=True
                    )
                )
                .distinct()
            )

        else:

            queryset = (
                queryset
                .filter(
                    topics__isnull=True
                )
                .distinct()
            )


    # =====================================================
    # Regions
    # =====================================================

    if enabled_region_ids is not None:

        if enabled_region_ids:

            queryset = (
                queryset
                .filter(
                    Q(
                        regions__id__in=enabled_region_ids
                    )
                    |
                    Q(
                        regions__isnull=True
                    )
                )
                .distinct()
            )

        else:

            queryset = (
                queryset
                .filter(
                    regions__isnull=True
                )
                .distinct()
            )


    # =====================================================
    # Sources
    # =====================================================

    if enabled_source_ids is not None:

        if enabled_source_ids:

            queryset = (
                queryset
                .filter(
                    source__id__in=enabled_source_ids
                )
            )

        else:

            queryset = queryset.none()


    return queryset

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
            "topics",
            "regions",
        )
    )


    # =====================================================
    # Favorite status
    # =====================================================

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


    # =====================================================
    # User preferences
    # =====================================================

    if preference is not None:


        # =================================================
        # Topics
        # =================================================

        hidden_topics = (
            preference
            .hidden_topics
            .all()
        )

        if hidden_topics.exists():

            visible_topics = (
                Topic.objects
                .filter(
                    is_active=True
                )
                .exclude(
                    id__in=hidden_topics.values_list(
                        "id",
                        flat=True,
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


        # =================================================
        # Regions
        # =================================================

        hidden_regions = (
            preference
            .hidden_regions
            .all()
        )

        if hidden_regions.exists():

            visible_regions = (
                Region.objects
                .filter(
                    is_active=True
                )
                .exclude(
                    id__in=hidden_regions.values_list(
                        "id",
                        flat=True,
                    )
                )
            )

            queryset = (
                queryset
                .filter(
                    Q(
                        regions__in=visible_regions
                    )
                    |
                    Q(
                        regions__isnull=True
                    )
                )
                .distinct()
            )


        # =================================================
        # Sources
        # =================================================

        hidden_sources = (
            preference
            .hidden_sources
            .all()
        )

        if hidden_sources.exists():

            visible_sources = (
                NewsSource.objects
                .filter(
                    is_active=True
                )
                .exclude(
                    id__in=hidden_sources.values_list(
                        "id",
                        flat=True,
                    )
                )
            )

            queryset = (
                queryset
                .filter(
                    source__in=visible_sources
                )
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
            _apply_public_news_settings(
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

    # =====================================================
    # Active tab
    # =====================================================

    active_tab = request.GET.get(
        "tab",
        "topics",
    )

    if active_tab not in {
        "topics",
        "regions",
        "sources",
    }:
        active_tab = "topics"

    # =====================================================
    # Topics
    # =====================================================

    topics = (
        Topic.objects
        .filter(
            is_active=True
        )
        .order_by(
            "display_order",
            "name",
        )
    )

    # =====================================================
    # Sources
    # =====================================================

    sources = (
        NewsSource.objects
        .filter(
            is_active=True
        )
        .order_by(
            "display_order",
            "name",
        )
    )

    # =====================================================
    # Regions
    # =====================================================

    regions = (
        Region.objects
        .filter(
            is_active=True
        )
        .order_by(
            "display_order",
            "name",
        )
    )

    # =====================================================
    # Logged-in user
    # =====================================================

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

    # =====================================================
    # Public / anonymous
    # =====================================================

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

    # =====================================================
    # Render
    # =====================================================

    return render(
        request,
        "news/topic_list.html",
        {
            "topics": topics,
            "regions": regions,
            "sources": sources,
            "active_tab": active_tab,
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
        )

        articles = (
            _apply_public_news_settings(
                articles,
                public_settings,
            )
        )

        articles = (
            articles
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

def source_detail(
    request,
    source_id,
):

    preference = None
    public_settings = None

    # =====================================================
    # Source
    # =====================================================

    source = get_object_or_404(
        NewsSource,
        id=source_id,
        is_active=True,
    )

    # =====================================================
    # Logged-in user
    # =====================================================

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
                source=source
            )
            .order_by(
                "-published_at"
            )[:100]
        )

    # =====================================================
    # Public / anonymous
    # =====================================================

    else:

        public_settings = (
            _get_public_settings(
                request
            )
        )

        articles = (
            _article_queryset()
            .filter(
                source=source
            )
        )

        articles = (
            _apply_public_news_settings(
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

    # =====================================================
    # Render
    # =====================================================

    return render(
        request,
        "news/source_detail.html",
        {
            "source": source,
            "articles": articles,
            "preference": preference,
            "public_settings": public_settings,
        },
    )

def region_detail(
    request,
    slug,
):

    preference = None
    public_settings = None

    region = get_object_or_404(
        Region,
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
                regions=region
            )
            .order_by(
                "-published_at"
            )[:100]
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
                regions=region
            )
        )

        articles = (
            _apply_public_news_settings(
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

    return render(
        request,
        "news/region_detail.html",
        {
            "region": region,
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


    # =====================================================
    # Active choices
    # =====================================================

    active_topics = (
        Topic.objects
        .filter(
            is_active=True
        )
        .order_by(
            "display_order",
            "name",
        )
    )

    active_regions = (
        Region.objects
        .filter(
            is_active=True
        )
        .order_by(
            "display_order",
            "name",
        )
    )

    active_sources = (
        NewsSource.objects
        .filter(
            is_active=True
        )
        .order_by(
            "display_order",
            "name",
        )
    )


    # =====================================================
    # Defaults
    # =====================================================

    default_topic_ids = list(
        active_topics.values_list(
            "id",
            flat=True,
        )
    )

    default_region_ids = list(
        active_regions.values_list(
            "id",
            flat=True,
        )
    )

    default_source_ids = list(
        active_sources.values_list(
            "id",
            flat=True,
        )
    )


    # =====================================================
    # POST
    # =====================================================

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

            enabled_regions = (
                form.cleaned_data[
                    "enabled_regions"
                ]
            )

            enabled_sources = (
                form.cleaned_data[
                    "enabled_sources"
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

                "enabled_region_ids": list(
                    enabled_regions.values_list(
                        "id",
                        flat=True,
                    )
                ),

                "enabled_source_ids": list(
                    enabled_sources.values_list(
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


    # =====================================================
    # GET
    # =====================================================

    else:

        public_settings = (
            request.session.get(
                "news_public_settings",
                {},
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

                "enabled_regions": (
                    public_settings.get(
                        "enabled_region_ids",
                        default_region_ids,
                    )
                ),

                "enabled_sources": (
                    public_settings.get(
                        "enabled_source_ids",
                        default_source_ids,
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

def about(request):

    preference = None
    public_settings = None

    if request.user.is_authenticated:
        preference = _get_preference(
            request.user
        )
    else:
        public_settings = _get_public_settings(
            request
        )

    if request.method == "POST":

        last_feedback_at = request.session.get(
            "news_feedback_last_sent_at"
        )

        if last_feedback_at:

            try:
                last_feedback_time = (
                    timezone.datetime.fromisoformat(
                        last_feedback_at
                    )
                )

                seconds_since_last_feedback = (
                    timezone.now()
                    - last_feedback_time
                ).total_seconds()

            except (
                TypeError,
                ValueError,
            ):
                seconds_since_last_feedback = 60

            if seconds_since_last_feedback < 60:

                messages.error(
                    request,
                    "コメントは少し時間をあけてから再度送信してください。",
                )

                return redirect(
                    "news:about"
                )

        form = NewsFeedbackForm(
            request.POST
        )

        if form.is_valid():

            form.save()

            request.session[
                "news_feedback_last_sent_at"
            ] = timezone.now().isoformat()

            request.session.modified = True

            messages.success(
                request,
                "ありがとうございます。コメントを送信しました。",
            )

            return redirect(
                "news:about"
            )

    else:

        form = NewsFeedbackForm()

    return render(
        request,
        "news/about.html",
        {
            "form": form,
            "preference": preference,
            "public_settings": public_settings,
        },
    )


def services(request):
    return render(
        request,
        "news/services.html",
    )