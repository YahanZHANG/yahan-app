from datetime import timedelta

from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Prefetch, Count
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from django.urls import reverse, reverse_lazy
from django.utils import timezone

from django.views.decorators.http import require_POST


from .models import (
    SwissBoardPost,
    SwissBoardProfile,
    SwissBoardComment,
    SwissBoardNotification
)
from .forms import (
    SwissBoardPostForm,
    SwissBoardProfileForm,
    SwissBoardCommentForm
)




MAIN_CATEGORIES = [
    {
        "name": "売買・譲渡",
        "icon": "bi-bag",
        "slug": "marketplace",
    },
    {
        "name": "住まい",
        "icon": "bi-house",
        "slug": "housing",
    },
    {
        "name": "仲間募集",
        "icon": "bi-people",
        "slug": "friends",
    },
    {
        "name": "育児・教育",
        "icon": "bi-balloon-heart",
        "slug": "parenting",
    },
    {
        "name": "おすすめ",
        "icon": "bi-heart",
        "slug": "recommendations",
    },
    {
        "name": "質問・雑談",
        "icon": "bi-chat-dots",
        "slug": "questions",
    },
]

FEATURED_TOPICS = [
    "Kita",
    "美容室",
    "ベビー用品",
    "日本食材",
    "テニス仲間",
]


# =========================================================
# Swiss Board Home
# =========================================================

def home(request):
    """
    スイス掲示板の公開ホーム画面。

    公開済み投稿を新着順に最大5件表示する。
    下書き・非公開の投稿は表示しない。
    """

    latest_posts = (
        SwissBoardPost.objects
        .filter(
            status=SwissBoardPost.Status.PUBLISHED
        )
        .order_by(
            "-created_at",
            "-id",
        )[:5]
    )

    context = {
        "main_categories": MAIN_CATEGORIES,
        "featured_topics": FEATURED_TOPICS,
        "posts": latest_posts,
    }

    return render(
        request,
        "swiss_board/home.html",
        context,
    )

# =========================================================
# Category menu
# =========================================================

BOARD_CATEGORIES = [
    {
        "slug": "marketplace",
        "name": "売買・譲渡・レンタル",
        "icon": "bi-bag",
        "subcategories": [
            "ベビー・子ども用品",
            "家具・インテリア",
            "家電",
            "PC・スマホ・電子機器",
            "キッチン・生活用品",
            "衣類・ファッション",
            "本・教材・マンガ",
            "自転車",
            "車・バイク",
            "スポーツ・アウトドア",
            "楽器・ホビー",
            "チケット",
            "その他",
        ],
    },
    {
        "slug": "housing",
        "name": "不動産・住まい",
        "icon": "bi-house",
        "subcategories": [
            "アパート・一戸建て",
            "WG・シェアハウス",
            "短期賃貸・一時滞在",
            "ルームメイト募集",
            "駐車場・ガレージ",
            "住宅購入・売却",
            "その他",
        ],
    },
    {
        "slug": "jobs",
        "name": "求人・仕事探し",
        "icon": "bi-briefcase",
        "subcategories": [
            "正社員・契約社員",
            "パート・アルバイト",
            "インターン・学生向け",
            "フリーランス・業務委託",
            "リモート・オンライン",
            "その他",
        ],
    },
    {
        "slug": "friends",
        "name": "仲間募集",
        "icon": "bi-people",
        "subcategories": [
            "ママ友・パパ友",
            "友人・交流",
            "スポーツ",
            "趣味・サークル",
            "語学交換・Tandem",
            "学生・留学生",
            "ボランティア",
            "その他",
        ],
    },
    {
        "slug": "events",
        "name": "イベント",
        "icon": "bi-calendar-event",
        "subcategories": [
            "交流会・パーティー",
            "子ども・家族向け",
            "スポーツ・アウトドア",
            "文化・芸術",
            "セミナー・講演会",
            "ビジネス・ネットワーキング",
            "日本関連行事",
            "その他",
        ],
    },
    {
        "slug": "lessons",
        "name": "レッスン・習い事",
        "icon": "bi-mortarboard",
        "subcategories": [
            "ドイツ語",
            "フランス語",
            "英語",
            "日本語",
            "その他の語学",
            "音楽・芸術",
            "スポーツ・ダンス",
            "学習支援・家庭教師",
            "プログラミング・IT",
            "その他",
        ],
    },
    {
        "slug": "parenting",
        "name": "育児・教育",
        "icon": "bi-balloon-heart",
        "subcategories": [
            "Kita・保育園",
            "幼稚園・学校",
            "補習校・日本語教育",
            "妊娠・出産",
            "乳幼児の育児",
            "子どもの遊び場・施設",
            "教育制度・進学",
            "その他",
        ],
    },
    {
        "slug": "services",
        "name": "サービス・ビジネス",
        "icon": "bi-tools",
        "subcategories": [
            "ベビーシッター・ナニー",
            "家事代行・清掃",
            "ペットシッター",
            "翻訳・通訳",
            "IT・Web",
            "引っ越し・配送",
            "美容・ウェルネス",
            "旅行・観光",
            "専門サービス",
            "その他",
        ],
    },
    {
        "slug": "recommendations",
        "name": "みんなのおすすめ",
        "icon": "bi-heart",
        "subcategories": [
            "レストラン・カフェ",
            "美容室・ヘアサロン",
            "日本食材店・アジア食材店",
            "買い物・ショップ",
            "子連れスポット",
            "観光・旅行先",
            "医療機関・歯科",
            "公園・自然・アウトドア",
            "その他",
        ],
    },
    {
        "slug": "questions",
        "name": "質問・雑談",
        "icon": "bi-chat-dots",
        "subcategories": [
            "スイス生活全般",
            "滞在許可・行政手続",
            "税金・保険",
            "交通・SBB",
            "買い物・生活用品",
            "銀行・通信・契約",
            "旅行・お出かけ",
            "雑談・その他",
        ],
    },
]


def category_menu(request):
    """
    公開カテゴリー一覧。
    現時点ではカテゴリー定義をPythonで管理する。
    """

    return render(
        request,
        "swiss_board/categories.html",
        {
            "categories": BOARD_CATEGORIES,
        },
    )

# =========================================================
# Post Detail
# =========================================================

def post_detail(request, pk):
    """
    公開済み投稿の詳細画面。

    投稿が存在しない、または非公開の場合は
    掲示板専用の404ページを表示する。
    """

    try:
        post = get_object_or_404(
            SwissBoardPost.objects.select_related(
                "author",
                "author__swiss_board_profile",
            ),
            pk=pk,
            status=SwissBoardPost.Status.PUBLISHED,
        )

    except Http404:
        return render(
            request,
            "swiss_board/post_not_found.html",
            status=404,
        )

    comments = get_post_comments(post)
    comment_count = post.comments.count()

    return render(
        request,
        "swiss_board/post_detail.html",
        {
            "post": post,
            "comments": comments,
            "comment_count": comment_count,
            "comment_form": SwissBoardCommentForm(),
        }
    )

# =========================================================
# Post Search
# =========================================================

def post_search(request):
    """
    公開投稿の検索画面。

    - Keyword
    - Category
    - Subcategory
    - Region
    - Sorting
    - Pagination

    Login is not required.
    """

    # -----------------------------------------------------
    # Search parameters
    # -----------------------------------------------------

    keyword = request.GET.get(
        "q", ""
    ).strip()[:100]

    category = request.GET.get(
        "category", ""
    ).strip()

    subcategory = request.GET.get(
        "subcategory", ""
    ).strip()[:100]

    region = request.GET.get(
        "region", ""
    ).strip()[:100]

    sort = request.GET.get(
        "sort", "newest"
    ).strip()

    # -----------------------------------------------------
    # Category and subcategory definitions
    # -----------------------------------------------------

    subcategories_by_category = {
        item["slug"]: item["subcategories"]
        for item in BOARD_CATEGORIES
    }

    valid_categories = {
        value
        for value, label
        in SwissBoardPost.Category.choices
    }

    # Invalid category -> all categories
    if category not in valid_categories:
        category = ""

    # Subcategory must belong to selected category
    valid_subcategories = subcategories_by_category.get(
        category,
        [],
    )

    if subcategory not in valid_subcategories:
        subcategory = ""

    # -----------------------------------------------------
    # Validate sorting
    # -----------------------------------------------------

    sort_options = {
        "newest": "新着順",
        "oldest": "古い順",
        "title": "タイトル順",
    }

    if sort not in sort_options:
        sort = "newest"

    # -----------------------------------------------------
    # Public posts only
    # -----------------------------------------------------

    posts = SwissBoardPost.objects.filter(
        status=SwissBoardPost.Status.PUBLISHED
    )

    # -----------------------------------------------------
    # Keyword
    # -----------------------------------------------------

    if keyword:
        posts = posts.filter(
            Q(title__icontains=keyword)
            | Q(body__icontains=keyword)
            | Q(subcategory__icontains=keyword)
        )

    # -----------------------------------------------------
    # Category
    # -----------------------------------------------------

    if category:
        posts = posts.filter(
            category=category
        )

    # -----------------------------------------------------
    # Subcategory
    # -----------------------------------------------------

    if subcategory:
        posts = posts.filter(
            subcategory__iexact=subcategory
        )

    # -----------------------------------------------------
    # Region
    # -----------------------------------------------------

    if region:
        posts = posts.filter(
            region__icontains=region
        )

    # -----------------------------------------------------
    # Sorting
    # -----------------------------------------------------

    ordering = {
        "newest": ("-created_at", "-id"),
        "oldest": ("created_at", "id"),
        "title": ("title", "-id"),
    }

    posts = posts.order_by(
        *ordering[sort]
    )

    # -----------------------------------------------------
    # Pagination
    # -----------------------------------------------------

    paginator = Paginator(
        posts,
        20,
    )

    page_obj = paginator.get_page(
        request.GET.get("page", 1)
    )

    # -----------------------------------------------------
    # Preserve search parameters
    # -----------------------------------------------------

    from urllib.parse import urlencode

    query_string = urlencode({
        "q": keyword,
        "category": category,
        "subcategory": subcategory,
        "region": region,
        "sort": sort,
    })

    # -----------------------------------------------------
    # Render
    # -----------------------------------------------------

    context = {
        "page_obj": page_obj,

        "keyword": keyword,

        "selected_category": category,
        "selected_subcategory": subcategory,
        "selected_region": region,
        "selected_sort": sort,

        "category_choices": (
            SwissBoardPost.Category.choices
        ),

        "subcategories_by_category": (
            subcategories_by_category
        ),

        "sort_options": sort_options,
        "query_string": query_string,
    }

    return render(
        request,
        "swiss_board/search.html",
        context,
    )


# =========================================================
# Create Post
# =========================================================

@login_required
def post_create(request):
    """
    ログイン済みユーザーの新規投稿。

    - サーバー側で投稿者を確定
    - カテゴリー・サブカテゴリーの入力を検証
    - 新規投稿は公開状態で保存
    """

    category_map = {
        item["slug"]: item["subcategories"]
        for item in BOARD_CATEGORIES
    }

    valid_categories = {
        value
        for value, label
        in SwissBoardPost.Category.choices
    }

    # -----------------------------------------------------
    # Initial values from HOME shortcuts
    # -----------------------------------------------------

    initial = {}

    if request.method == "GET":

        selected_category = request.GET.get(
            "category", ""
        )

        if selected_category in valid_categories:
            initial["category"] = selected_category

        intent = request.GET.get(
            "intent", ""
        )

        if intent == "wanted":
            initial["title"] = "【探しています】"

        elif intent == "sell":
            initial["title"] = "【売ります】"

    # -----------------------------------------------------
    # Form
    # -----------------------------------------------------

    form = SwissBoardPostForm(
        request.POST if request.method == "POST" else None,
        initial=initial,
        category_map=category_map,
    )

    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    if request.method == "POST" and form.is_valid():

        # Basic protection against rapid repeated posting.
        recently_posted = SwissBoardPost.objects.filter(
            author=request.user,
            created_at__gte=(
                timezone.now() - timedelta(seconds=60)
            ),
        ).exists()

        if recently_posted:

            form.add_error(
                None,
                "連続投稿を防ぐため、前回の投稿から"
                "1分以上空けてください。",
            )

        else:

            post = form.save(commit=False)

            post.author = request.user

            post.status = (
                SwissBoardPost.Status.PUBLISHED
            )

            post.save()

            return redirect(
                "swiss_board:post_detail",
                pk=post.pk,
            )

    # -----------------------------------------------------
    # Render
    # -----------------------------------------------------

    return render(
        request,
        "swiss_board/post_form.html",
        {
            "form": form,
            "subcategories_by_category": category_map,
        },
    )


# =========================================================
# My Posts
# =========================================================

@login_required
def my_posts(request):
    """
    ログインユーザー自身の投稿一覧。

    公開、下書き、非公開を含む。
    """

    posts = (
        SwissBoardPost.objects
        .filter(author=request.user)
        .order_by("-created_at", "-id")
    )

    paginator = Paginator(posts, 20)

    page_obj = paginator.get_page(
        request.GET.get("page", 1)
    )

    return render(
        request,
        "swiss_board/my_posts.html",
        {
            "page_obj": page_obj,
        },
    )


# =========================================================
# Edit Post
# =========================================================

@login_required
def post_edit(request, pk):
    """
    自分の投稿のみ編集可能。

    公開状態は変更しない。
    管理者が非公開にした投稿を、
    編集によって再公開させない。
    """

    post = get_object_or_404(
        SwissBoardPost,
        pk=pk,
        author=request.user,
    )

    category_map = {
        item["slug"]: item["subcategories"]
        for item in BOARD_CATEGORIES
    }

    # -----------------------------------------------------
    # Existing region
    # -----------------------------------------------------

    region = post.region or ""

    known_regions = {
        value
        for value, label
        in SwissBoardPostForm.REGION_CHOICES
        if value and value != "other"
    }

    region_initial = {}

    if region in known_regions:
        region_initial["region_choice"] = region

    elif region:
        region_initial["region_choice"] = "other"
        region_initial["region_other"] = region

    else:
        region_initial["region_choice"] = ""

    # -----------------------------------------------------
    # Form
    # -----------------------------------------------------

    form = SwissBoardPostForm(
        request.POST if request.method == "POST" else None,
        instance=post,
        initial=region_initial,
        category_map=category_map,
    )

    if request.method == "POST" and form.is_valid():

        # Do not change author or publication status.
        form.save()

        # Public posts have a detail page.
        if post.status == SwissBoardPost.Status.PUBLISHED:

            return redirect(
                "swiss_board:post_detail",
                pk=post.pk,
            )

        return redirect(
            "swiss_board:my_posts"
        )

    return render(
        request,
        "swiss_board/post_form.html",
        {
            "form": form,
            "is_edit": True,
            "subcategories_by_category": category_map,
        },
    )


# =========================================================
# Delete Post
# =========================================================

@login_required
def post_delete(request, pk):
    """
    自分の投稿のみ削除可能。

    削除処理はPOSTリクエストのみ。
    """

    post = get_object_or_404(
        SwissBoardPost,
        pk=pk,
        author=request.user,
    )

    if request.method == "POST":

        post.delete()

        return redirect(
            "swiss_board:my_posts"
        )

    return render(
        request,
        "swiss_board/post_confirm_delete.html",
        {
            "post": post,
        },
    )

# =========================================================
# Swiss Board My Page
# =========================================================

@login_required
@login_required
def my_page(request):

    my_post_count = SwissBoardPost.objects.filter(
        author=request.user,
    ).count()

    my_question_count = SwissBoardPost.objects.filter(
        author=request.user,
        category=SwissBoardPost.Category.QUESTIONS,
    ).count()

    unread_notification_count = (
        SwissBoardNotification.objects
        .filter(
            recipient=request.user,
            is_read=False,
        )
        .count()
    )

    return render(
        request,
        "swiss_board/my_page.html",
        {
            "my_post_count": my_post_count,
            "my_question_count": my_question_count,
            "unread_notification_count":unread_notification_count,
        },
    )


from django.contrib.auth.views import (
    PasswordChangeView,
    PasswordChangeDoneView,
)
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


class YappPasswordChangeView(PasswordChangeView):

    def get_success_url(self):

        next_url = self.request.POST.get(
            "next",
            self.request.GET.get("next", ""),
        )

        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return (
                reverse("password_change_done")
                + "?next="
                + next_url
            )

        return reverse("password_change_done")


class YappPasswordChangeDoneView(PasswordChangeDoneView):

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        next_url = self.request.GET.get("next", "")

        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            context["return_url"] = next_url
        else:
            context["return_url"] = "/"

        return context


# =========================================================
# Edit Swiss Board Profile
# =========================================================

@login_required
def profile_edit(request):
    """
    Swiss Board専用プロフィールの編集。

    Yapp共通プロフィールは変更しない。
    """

    profile, created = (
        SwissBoardProfile.objects.get_or_create(
            user=request.user,
        )
    )

    form = SwissBoardProfileForm(
        request.POST if request.method == "POST" else None,
        instance=profile,
    )

    if request.method == "POST" and form.is_valid():

        form.save()

        return redirect(
            "swiss_board:my_page"
        )

    return render(
        request,
        "swiss_board/profile_edit.html",
        {
            "form": form,
        },
    )

# =========================================================
# Create Comment / Reply + Notification
# =========================================================

@login_required
@require_POST
def comment_create(request, pk):

    post = get_object_or_404(
        SwissBoardPost,
        pk=pk,
        status=SwissBoardPost.Status.PUBLISHED,
    )

    # =====================================================
    # Parent comment
    # =====================================================

    parent_id = request.POST.get("parent", "").strip()
    parent = None

    if parent_id:

        parent = get_object_or_404(
            SwissBoardComment,
            pk=parent_id,
            post=post,
            parent__isnull=True,
        )

    # =====================================================
    # Form validation
    # =====================================================

    form = SwissBoardCommentForm(request.POST)

    if form.is_valid():

        # コメントと通知をまとめて保存
        with transaction.atomic():

            comment = form.save(commit=False)

            comment.post = post
            comment.author = request.user
            comment.parent = parent

            comment.save()

            # =============================================
            # Notification recipients
            # =============================================

            recipients = {}

            # 投稿者への通知
            if post.author_id != request.user.pk:

                recipients[post.author_id] = (
                    SwissBoardNotification.Kind.COMMENT
                )

            # 返信先コメントの作者への通知
            if parent is not None:

                if parent.author_id != request.user.pk:

                    recipients[parent.author_id] = (
                        SwissBoardNotification.Kind.REPLY
                    )

            # =============================================
            # Create notifications
            # =============================================

            for recipient_id, kind in recipients.items():

                SwissBoardNotification.objects.create(
                    recipient_id=recipient_id,
                    actor=request.user,
                    comment=comment,
                    kind=kind,
                )

        # =================================================
        # Redirect to new comment
        # =================================================

        return redirect(
            reverse(
                "swiss_board:post_detail",
                kwargs={"pk": post.pk},
            )
            + f"#comment-{comment.pk}"
        )

    # =====================================================
    # Invalid form
    # =====================================================

    context = {
        "post": post,
        "comments": get_post_comments(post),
        "comment_count": post.comments.count(),
        "comment_form": (
            form if parent is None
            else SwissBoardCommentForm()
        ),
        "reply_form": form if parent else None,
        "reply_error_parent_id": (
            parent.pk if parent else None
        ),
    }

    return render(
        request,
        "swiss_board/post_detail.html",
        context,
        status=400,
    )

# =========================================================
# My Comments
# =========================================================

@login_required
def my_comments(request):
    """
    自分が投稿したコメントの一覧。
    非公開・削除済みの元投稿は表示しない。
    """

    comments = (
        SwissBoardComment.objects
        .filter(
            author=request.user,
            post__status=SwissBoardPost.Status.PUBLISHED,
        )
        .select_related("post")
        .order_by("-created_at", "-pk")
    )

    paginator = Paginator(comments, 20)

    page_obj = paginator.get_page(
        request.GET.get("page", 1)
    )

    return render(
        request,
        "swiss_board/my_comments.html",
        {
            "page_obj": page_obj,
        },
    )   


# =========================================================
# Comment Query
# =========================================================

def get_post_comments(post):

    reply_queryset = (
        SwissBoardComment.objects
        .filter(parent__isnull=False)
        .select_related(
            "author",
            "author__swiss_board_profile",
        )
        .order_by("created_at", "pk")
    )

    return (
        SwissBoardComment.objects
        .filter(
            post=post,
            parent__isnull=True,
        )
        .select_related(
            "author",
            "author__swiss_board_profile",
        )
        .prefetch_related(
            Prefetch(
                "replies",
                queryset=reply_queryset,
            )
        )
        .order_by("created_at", "pk")
    )


# =========================================================
# Edit Comment
# =========================================================

@login_required
def comment_edit(request, pk):

    comment = get_object_or_404(
        SwissBoardComment.objects.select_related("post"),
        pk=pk,
        author=request.user,
        post__status=SwissBoardPost.Status.PUBLISHED,
    )

    form = SwissBoardCommentForm(
        request.POST if request.method == "POST" else None,
        instance=comment,
    )

    if request.method == "POST" and form.is_valid():

        form.save()

        return redirect(
            reverse(
                "swiss_board:post_detail",
                kwargs={"pk": comment.post_id},
            )
            + f"#comment-{comment.pk}"
        )

    return render(
        request,
        "swiss_board/comment_form.html",
        {
            "form": form,
            "comment": comment,
        },
    )

# =========================================================
# Delete Comment
# =========================================================

@login_required
def comment_delete(request, pk):

    comment = get_object_or_404(
        SwissBoardComment.objects.select_related("post"),
        pk=pk,
        author=request.user,
        post__status=SwissBoardPost.Status.PUBLISHED,
    )

    post_pk = comment.post_id

    if request.method == "POST":

        comment.delete()

        return redirect(
            reverse(
                "swiss_board:post_detail",
                kwargs={"pk": post_pk},
            )
            + "#comments"
        )

    return render(
        request,
        "swiss_board/comment_confirm_delete.html",
        {
            "comment": comment,
        },
    )

# =========================================================
# Swiss Board 404
# =========================================================

def page_not_found(request, exception=None):

    return render(
        request,
        "swiss_board/page_not_found.html",
        status=404,
    )


# =========================================================
# My Questions
# =========================================================

@login_required
def my_questions(request):

    questions = (
        SwissBoardPost.objects
        .filter(
            author=request.user,
            category=SwissBoardPost.Category.QUESTIONS,
        )
        .annotate(
            answer_count=Count("comments"),
        )
        .order_by("-created_at", "-pk")
    )

    paginator = Paginator(questions, 20)

    page_obj = paginator.get_page(
        request.GET.get("page", 1)
    )

    return render(
        request,
        "swiss_board/my_questions.html",
        {
            "page_obj": page_obj,
        },
    )

# =========================================================
# Notifications
# =========================================================

@login_required
def my_notifications(request):

    notifications = (
        SwissBoardNotification.objects
        .filter(recipient=request.user)
        .select_related(
            "actor",
            "actor__swiss_board_profile",
            "comment",
            "comment__post",
        )
        .order_by("-created_at", "-pk")
    )

    paginator = Paginator(notifications, 20)

    page_obj = paginator.get_page(
        request.GET.get("page", 1)
    )

    return render(
        request,
        "swiss_board/my_notifications.html",
        {
            "page_obj": page_obj,
        },
    )


# =========================================================
# Open Notification
# =========================================================

@login_required
@require_POST
def notification_open(request, pk):

    notification = get_object_or_404(
        SwissBoardNotification.objects.select_related(
            "comment",
            "comment__post",
        ),
        pk=pk,
        recipient=request.user,
    )

    if not notification.is_read:

        notification.is_read = True
        notification.save(
            update_fields=["is_read"]
        )

    comment = notification.comment

    if comment.post.status != SwissBoardPost.Status.PUBLISHED:
        return redirect("swiss_board:my_notifications")

    return redirect(
        reverse(
            "swiss_board:post_detail",
            kwargs={"pk": comment.post_id},
        )
        + f"#comment-{comment.pk}"
    )

