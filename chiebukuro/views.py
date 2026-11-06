"""
スイス生活の知恵袋 (掲示板) の画面。

メニュー: HOME・つぶやき・質問・ゆずりあい・募集告知 (+ 右上に🔔とマイページ)
読むのはだれでも (公開前は運営だけ)。書く・押すにはログインが必要。
"""

import logging
from datetime import date
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import (
    BOARD_REGION_CHOICES,
    THEME_CHOICES,
    Answer,
    BoardProfile,
    BoardSettings,
    Genre,
    Interest,
    Item,
    ItemRequest,
    Message,
    Notice,
    Notification,
    Post,
    PostLike,
    PostReply,
    Question,
    Report,
    Status,
    Thanks,
)
from .services import (
    best_answers,
    notify,
    question_list,
    short,
    unread_notifications,
    user_nickname,
    waiting_questions,
)


logger = logging.getLogger(__name__)

QUESTION_MAX_LENGTH = 200
ANSWER_MAX_LENGTH = 2000
POST_MAX_LENGTH = 500
MESSAGE_MAX_LENGTH = 1000
ITEM_TITLE_MAX_LENGTH = 80
ITEM_BODY_MAX_LENGTH = 1000
NOTICE_BODY_MAX_LENGTH = 1500
PER_PAGE = 20
POSTS_PER_PAGE = 30

THEME_LABELS = dict(THEME_CHOICES)
REGION_LABELS = dict(BOARD_REGION_CHOICES)

# テーマの並び (「その他」は最後)
THEME_ORDER = [value for value, _ in THEME_CHOICES if value != "other"] + ["other"]
THEMES = [(value, THEME_LABELS[value]) for value in THEME_ORDER]


# =========================================================
# 共通
# =========================================================

def board_open(view):
    """公開前は、運営 (スタッフ) だけが見られる"""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not BoardSettings.current().is_open and not request.user.is_staff:
            return render(request, "chiebukuro/closed.html", status=200)
        return view(request, *args, **kwargs)

    return wrapper


def clean_choice(value, choices):
    return value if value in dict(choices) else ""


def login_url(request):
    return f"{reverse('login')}?next={request.get_full_path()}"


def safe_next(request, fallback):
    next_url = request.POST.get("next") or ""
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    return fallback


def current_region(request):
    """
    見ている地域。?region= で選ぶと、ほかのページでも同じ地域のまま。
    まだ選んでいなければ、プロフィールの「住んでいる地域」。空 = スイス全体。
    """

    if "region" in request.GET:
        region = clean_choice(request.GET.get("region", ""), BOARD_REGION_CHOICES)
        request.session["cb_region"] = region
        return region
    if "cb_region" in request.session:
        return clean_choice(request.session["cb_region"], BOARD_REGION_CHOICES)
    if request.user.is_authenticated:
        profile = BoardProfile.objects.filter(user=request.user).first()
        if profile:
            return profile.region
    return ""


def by_region(queryset, region, field="region"):
    """その地域のものと、地域なし (スイス全体) のもの"""

    if not region:
        return queryset
    return queryset.filter(Q(**{field: region}) | Q(**{field: ""}))


# 右下の「＋」ボタン: いま見ているページに合わせて変わる
FAB = {
    "home": ("書く", "chiebukuro:new"),
    "posts": ("つぶやく", "chiebukuro:post_new"),
    "questions": ("質問する", "chiebukuro:ask"),
    "items": ("出す", "chiebukuro:item_new"),
    "notices": ("告知する", "chiebukuro:notice_new"),
}


def board_context(request, tab, region=None):
    fab = FAB.get(tab)
    return {
        "tab": tab,
        "board_is_open": BoardSettings.current().is_open,
        "unread": unread_notifications(request.user),
        "fab_label": fab[0] if fab else "",
        "fab_url": reverse(fab[1]) if fab else "",
        "region": region or "",
        "region_label": REGION_LABELS.get(region or "", ""),
        "regions": BOARD_REGION_CHOICES,
    }


def my_talks(user):
    return (
        ItemRequest.objects
        .filter(Q(requester=user) | Q(item__owner=user) | Q(notice__owner=user))
        .select_related("item", "notice")
        .order_by("-last_message_at")
    )


def upload_board_photo(uploaded_file):
    """写真を小さくして Cloudinary に保存 (和食・おでかけと同じ仕組み)"""

    from outings.services.user_event_cloudinary import upload_user_event_photo
    from outings.services.user_event_images import process_user_event_image

    processed = process_user_event_image(uploaded_file, max_size=1200, quality=78)
    return upload_user_event_photo(processed, folder="yapp/board/items", filename="photo.webp")


def annotate_posts(queryset):
    return queryset.annotate(
        reply_total=Count("replies", filter=Q(replies__status=Status.PUBLISHED), distinct=True),
        like_total=Count("likes", distinct=True),
    )


def mark_liked(posts, user):
    liked = set()
    if user.is_authenticated:
        liked = set(PostLike.objects.filter(user=user, post__in=[post.pk for post in posts]).values_list("post_id", flat=True))
    for post in posts:
        post.liked = post.pk in liked
    return posts


def active_notices():
    return Notice.objects.filter(status=Status.PUBLISHED, expires_at__gt=timezone.now())


def open_items():
    return Item.objects.filter(status=Status.PUBLISHED).exclude(state=Item.State.DONE)


# =========================================================
# HOME: 各コーナーの新しいものを少しずつ
# =========================================================

@board_open
def home(request):

    region = current_region(request)

    posts = mark_liked(list(
        annotate_posts(by_region(Post.objects.filter(status=Status.PUBLISHED), region))
        .order_by("-created_at")[:4]
    ), request.user)

    waiting = waiting_questions(region=region, limit=4)
    answered = best_answers(list(
        question_list(region=region, sort="new").filter(answer_total__gt=0)[:4]
    ))

    items = list(by_region(open_items(), region).order_by("-created_at")[:4])
    notices = list(by_region(active_notices(), region).order_by("-created_at")[:4])

    return render(
        request,
        "chiebukuro/home.html",
        {
            **board_context(request, "home", region),
            "posts": posts,
            "waiting": waiting,
            "answered": answered,
            "items": items,
            "notices": notices,
        },
    )


# =========================================================
# つぶやき
# =========================================================

@board_open
def post_list(request):
    """つぶやきだけのタイムライン。いちばん上で、すぐつぶやける。"""

    region = current_region(request)
    theme = clean_choice(request.GET.get("theme", ""), THEME_CHOICES)

    posts = by_region(Post.objects.filter(status=Status.PUBLISHED), region)
    if theme:
        posts = posts.filter(theme=theme)
    page = Paginator(annotate_posts(posts).order_by("-created_at", "-pk"), POSTS_PER_PAGE).get_page(request.GET.get("page"))
    mark_liked(page.object_list, request.user)

    return render(
        request,
        "chiebukuro/posts.html",
        {
            **board_context(request, "posts", region),
            "page": page,
            "theme": theme,
            "themes": THEMES,
            "max_length": POST_MAX_LENGTH,
        },
    )


@board_open
@login_required
def post_new(request):

    error = ""
    body = (request.POST.get("body") or "").strip() if request.method == "POST" else ""
    theme = clean_choice(request.POST.get("theme", "") if request.method == "POST" else request.GET.get("theme", ""), THEME_CHOICES)
    region = clean_choice(request.POST.get("post_region", ""), BOARD_REGION_CHOICES) if request.method == "POST" else current_region(request)

    if request.method == "POST":
        if not body:
            error = "つぶやく内容を入力してください。"
        elif len(body) > POST_MAX_LENGTH:
            error = f"つぶやきは{POST_MAX_LENGTH}文字までです。"
        else:
            recent = Post.objects.filter(author=request.user, body=body).first()
            post = recent or Post.objects.create(
                body=body,
                theme=theme,
                region=region,
                author=request.user,
                nickname=user_nickname(request.user),
            )
            if recent is None:
                notify_staff(request, "新しいつぶやき", post.body, reverse("admin:chiebukuro_post_change", args=[post.pk]))
            return redirect("chiebukuro:posts")

    return render(
        request,
        "chiebukuro/post_form.html",
        {
            **board_context(request, "posts", current_region(request)),
            "body": body,
            "theme": theme,
            "post_region": region,
            "themes": THEMES,
            "error": error,
            "max_length": POST_MAX_LENGTH,
            "nickname": user_nickname(request.user),
        },
    )


@board_open
def post_detail(request, pk):

    post = get_object_or_404(Post.objects.select_related("author"), pk=pk)
    if post.status != Status.PUBLISHED and not request.user.is_staff:
        raise Http404

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect(login_url(request))
        body = (request.POST.get("body") or "").strip()[:ANSWER_MAX_LENGTH]
        if body and not post.replies.filter(author=request.user, body=body).exists():
            PostReply.objects.create(post=post, body=body, author=request.user, nickname=user_nickname(request.user))
            notify(
                post.author,
                Notification.Kind.REPLY,
                f"あなたのつぶやき「{short(post.body, 24)}」に返信がありました",
                reverse("chiebukuro:post", args=[pk]) + "#replies",
                actor=request.user,
            )
        return redirect(reverse("chiebukuro:post", args=[pk]) + "#replies")

    post.liked = request.user.is_authenticated and post.likes.filter(user=request.user).exists()
    post.like_total = post.likes.count()

    return render(
        request,
        "chiebukuro/post.html",
        {
            **board_context(request, "posts", current_region(request)),
            "post": post,
            "replies": post.replies.filter(status=Status.PUBLISHED),
            "login_url": login_url(request),
        },
    )


@board_open
@require_POST
@login_required
def toggle_post_like(request, pk):

    post = get_object_or_404(Post, pk=pk, status=Status.PUBLISHED)
    if post.author_id != request.user.pk:
        deleted, _ = PostLike.objects.filter(post=post, user=request.user).delete()
        if not deleted:
            try:
                PostLike.objects.create(post=post, user=request.user)
            except IntegrityError:
                pass
    return redirect(safe_next(request, reverse("chiebukuro:post", args=[pk])))


@board_open
@require_POST
@login_required
def delete_post(request, pk):

    post = get_object_or_404(Post, pk=pk, author=request.user)
    post.status = Status.HIDDEN
    post.save(update_fields=["status"])
    messages.success(request, "つぶやきを消しました。")
    return redirect("chiebukuro:posts")


@board_open
def new_choice(request):
    """HOME の「＋」: 何を書くか選ぶ"""

    return render(request, "chiebukuro/new.html", board_context(request, "new", current_region(request)))


# =========================================================
# 質問と答え
# =========================================================

QUESTION_SORTS = {
    "new": "新着",
    "open": "答え募集中",
    "popular": "人気",
}


@board_open
def question_index(request):

    region = current_region(request)
    sort = request.GET.get("sort", "new")
    if sort not in QUESTION_SORTS:
        sort = "new"
    theme = clean_choice(request.GET.get("theme", ""), THEME_CHOICES)
    query = (request.GET.get("q") or "").strip()[:60]

    if sort == "popular":
        questions = question_list(theme, region, "wanted", query).filter(answer_total__gt=0)
    else:
        questions = question_list(theme, region, sort, query)

    page = Paginator(questions, PER_PAGE).get_page(request.GET.get("page"))
    best_answers(page.object_list)

    return render(
        request,
        "chiebukuro/questions.html",
        {
            **board_context(request, "questions", region),
            "page": page,
            "sort": sort,
            "sorts": QUESTION_SORTS,
            "theme": theme,
            "themes": THEMES,
            "query": query,
            "open_total": question_list(theme, region, "open").count(),
        },
    )


@board_open
def question_detail(request, pk):

    question = get_object_or_404(Question, pk=pk)
    if question.status != Status.PUBLISHED and not request.user.is_staff:
        raise Http404

    error = ""
    draft = ""

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect(login_url(request))

        draft = (request.POST.get("body") or "").strip()
        if not draft:
            error = "答えを入力してください。"
        elif len(draft) > ANSWER_MAX_LENGTH:
            error = f"答えは{ANSWER_MAX_LENGTH}文字までです。"
        else:
            # 二度押し: 同じ人の同じ答えがもうあれば追加しない
            if not question.answers.filter(author=request.user, body=draft).exists():
                answer = Answer.objects.create(
                    question=question,
                    body=draft,
                    author=request.user,
                    nickname=user_nickname(request.user),
                )
                Question.objects.filter(pk=question.pk).update(last_answered_at=answer.created_at)
                notify_answer(request, question, answer)
            messages.success(request, "答えを書き込みました。ありがとうございます！")
            return redirect(reverse("chiebukuro:question", args=[question.pk]) + "#answers")

    # 参考になった数の多い順 (同じなら古い順)。いちばん上を「いちばん参考になった」として目立たせる
    answers = list(
        question.answers.filter(status=Status.PUBLISHED)
        .annotate(thanks_total=Count("thanks"))
        .order_by("-thanks_total", "created_at")
    )
    best_answer = answers[0] if answers and answers[0].thanks_total > 0 else None
    thanked = set()
    interested = False
    if request.user.is_authenticated:
        thanked = set(Thanks.objects.filter(user=request.user, answer__question=question).values_list("answer_id", flat=True))
        interested = Interest.objects.filter(user=request.user, question=question).exists()

    related = list(
        Question.objects.filter(status=Status.PUBLISHED, theme=question.theme)
        .exclude(pk=question.pk)
        .annotate(answer_total=Count("answers", filter=Q(answers__status=Status.PUBLISHED)))
        .order_by("-last_answered_at", "-created_at")[:5]
    )

    return render(
        request,
        "chiebukuro/question.html",
        {
            **board_context(request, "questions", current_region(request)),
            "question": question,
            "theme_label": THEME_LABELS.get(question.theme, ""),
            "question_region": REGION_LABELS.get(question.region, ""),
            "answers": answers,
            "best_answer": best_answer,
            "thanked": thanked,
            "interested": interested,
            "interest_total": question.interests.count() + question.survey_interest_count,
            "error": error,
            "draft": draft,
            "max_length": ANSWER_MAX_LENGTH,
            "related": related,
            "login_url": login_url(request),
        },
    )


def notify_answer(request, question, answer):
    """質問した人と「私も知りたい」を押した人に、答えがついたと知らせる"""

    url = reverse("chiebukuro:question", args=[question.pk]) + f"#a{answer.pk}"
    if question.author_id:
        notify(question.author, Notification.Kind.ANSWER, f"あなたの質問「{short(question.body, 24)}」に答えがつきました", url, actor=request.user)
    interests = question.interests.select_related("user")
    if question.author_id:
        interests = interests.exclude(user_id=question.author_id)
    for interest in interests:
        notify(interest.user, Notification.Kind.ANSWER, f"知りたい質問「{short(question.body, 24)}」に答えがつきました", url, actor=request.user)


@board_open
@login_required
def ask(request):

    error = ""
    body = ""
    theme = clean_choice(request.GET.get("theme", ""), THEME_CHOICES)
    region = ""

    if request.method == "POST":
        body = (request.POST.get("body") or "").strip()
        theme = clean_choice(request.POST.get("theme", ""), THEME_CHOICES)
        region = clean_choice(request.POST.get("question_region", ""), BOARD_REGION_CHOICES)

        if not body:
            error = "質問を入力してください。"
        elif len(body) > QUESTION_MAX_LENGTH:
            error = f"質問は{QUESTION_MAX_LENGTH}文字までです。"
        elif not theme:
            error = "テーマを選んでください。"
        else:
            question = Question.objects.filter(author=request.user, body=body).first()
            if question is None:
                question = Question.objects.create(
                    body=body,
                    theme=theme,
                    region=region,
                    source=Question.Source.MEMBER,
                    author=request.user,
                    nickname=user_nickname(request.user),
                )
                notify_staff(request, "新しい質問", question.body, reverse("admin:chiebukuro_question_change", args=[question.pk]))
            messages.success(request, "質問を書き込みました。答えがついたら🔔でお知らせします。")
            return redirect("chiebukuro:question", pk=question.pk)

    return render(
        request,
        "chiebukuro/ask.html",
        {
            **board_context(request, "questions", current_region(request)),
            "body": body,
            "theme": theme,
            "question_region": region,
            "themes": THEMES,
            "error": error,
            "max_length": QUESTION_MAX_LENGTH,
            "nickname": user_nickname(request.user),
        },
    )


@board_open
@require_POST
@login_required
def toggle_interest(request, pk):

    question = get_object_or_404(Question, pk=pk, status=Status.PUBLISHED)
    deleted, _ = Interest.objects.filter(question=question, user=request.user).delete()
    if not deleted:
        try:
            Interest.objects.create(question=question, user=request.user)
        except IntegrityError:
            pass
    return redirect(safe_next(request, reverse("chiebukuro:question", args=[pk])))


@board_open
@require_POST
@login_required
def toggle_thanks(request, pk):

    answer = get_object_or_404(Answer, pk=pk, status=Status.PUBLISHED)
    if answer.author_id != request.user.pk:
        deleted, _ = Thanks.objects.filter(answer=answer, user=request.user).delete()
        if not deleted:
            try:
                Thanks.objects.create(answer=answer, user=request.user)
            except IntegrityError:
                pass
    return redirect(reverse("chiebukuro:question", args=[answer.question_id]) + f"#a{answer.pk}")


@board_open
@require_POST
@login_required
def delete_answer(request, pk):

    answer = get_object_or_404(Answer, pk=pk, author=request.user)
    question_id = answer.question_id
    answer.delete()
    messages.success(request, "答えを消しました。")
    return redirect("chiebukuro:question", pk=question_id)


# =========================================================
# ゆずりあい
# =========================================================

@board_open
def item_list(request):

    region = current_region(request)
    kind = clean_choice(request.GET.get("kind", ""), Item.Kind.choices)
    genre = clean_choice(request.GET.get("genre", ""), Genre.choices)
    show_done = request.GET.get("all") == "1"

    items = by_region(Item.objects.filter(status=Status.PUBLISHED), region)
    if kind:
        items = items.filter(kind=kind)
    if genre:
        items = items.filter(genre=genre)
    if not show_done:
        items = items.exclude(state=Item.State.DONE)
    items = items.annotate(request_total=Count("requests")).order_by("-created_at")

    page = Paginator(items, PER_PAGE).get_page(request.GET.get("page"))

    return render(
        request,
        "chiebukuro/items.html",
        {
            **board_context(request, "items", region),
            "page": page,
            "kind": kind,
            "kinds": Item.Kind.choices,
            "genre": genre,
            "genres": Genre.choices,
            "show_done": show_done,
        },
    )


ITEM_HINTS = {
    "give": ("ゆずる物", "例: ベビーカー（2019年製）", "サイズ・状態・受け渡しできる日など"),
    "want": ("さがしている物", "例: 子ども用のスキーブーツ 20cm", "サイズ・いつまでにほしいかなど"),
    "lend": ("貸せる物", "例: 日本語の絵本 10冊", "貸せる期間・返し方など"),
    "borrow": ("借りたい物", "例: スーツケース（大）", "いつからいつまでか・使い道など"),
}


@board_open
@login_required
def item_new(request):

    error = ""
    kind = clean_choice(request.POST.get("kind", "") if request.method == "POST" else request.GET.get("kind", ""), Item.Kind.choices) or Item.Kind.GIVE
    values = {"title": "", "body": "", "genre": "", "item_region": current_region(request), "place": ""}

    if request.method == "POST":
        values = {
            "title": (request.POST.get("title") or "").strip(),
            "body": (request.POST.get("body") or "").strip(),
            "genre": clean_choice(request.POST.get("genre", ""), Genre.choices),
            "item_region": clean_choice(request.POST.get("item_region", ""), BOARD_REGION_CHOICES),
            "place": (request.POST.get("place") or "").strip()[:80],
        }
        photo = request.FILES.get("photo")

        if not values["title"]:
            error = "品物の名前を入力してください。"
        elif len(values["title"]) > ITEM_TITLE_MAX_LENGTH:
            error = f"名前は{ITEM_TITLE_MAX_LENGTH}文字までです。"
        elif len(values["body"]) > ITEM_BODY_MAX_LENGTH:
            error = f"説明は{ITEM_BODY_MAX_LENGTH}文字までです。"
        elif not values["genre"]:
            error = "ジャンルを選んでください。"
        elif request.POST.get("agree") != "yes":
            error = "ルールを確認して、チェックを入れてください。"
        else:
            photo_url = ""
            if photo:
                try:
                    photo_url = upload_board_photo(photo)
                except (ValidationError, Exception):
                    logger.exception("board photo upload failed")
                    error = "写真を保存できませんでした。写真なしで出すか、別の写真を選んでください。"
            if not error:
                item = Item.objects.create(
                    kind=kind,
                    genre=values["genre"],
                    title=values["title"],
                    body=values["body"],
                    region=values["item_region"],
                    place=values["place"],
                    owner=request.user,
                    nickname=user_nickname(request.user),
                    photo_url=photo_url,
                )
                notify_staff(request, f"新しい「{item.get_kind_display()}」", item.title, reverse("admin:chiebukuro_item_change", args=[item.pk]))
                messages.success(request, f"書き込みました。「{item.request_word}」が届いたら🔔でお知らせします。")
                return redirect("chiebukuro:item", pk=item.pk)

    hint = ITEM_HINTS[kind]
    return render(
        request,
        "chiebukuro/item_form.html",
        {
            **board_context(request, "items", current_region(request)),
            "kind": kind,
            "kinds": Item.Kind.choices,
            "genres": Genre.choices,
            "values": values,
            "error": error,
            "title_max": ITEM_TITLE_MAX_LENGTH,
            "body_max": ITEM_BODY_MAX_LENGTH,
            "title_label": hint[0],
            "title_placeholder": hint[1],
            "body_placeholder": hint[2],
        },
    )


@board_open
def item_detail(request, pk):

    item = get_object_or_404(Item.objects.select_related("owner"), pk=pk)
    if item.status != Status.PUBLISHED and not request.user.is_staff and request.user.pk != item.owner_id:
        raise Http404

    my_request = None
    requests_for_owner = []
    if request.user.is_authenticated:
        if request.user.pk == item.owner_id:
            requests_for_owner = list(item.requests.order_by("-is_chosen", "created_at"))
        else:
            my_request = item.requests.filter(requester=request.user).first()

    return render(
        request,
        "chiebukuro/item.html",
        {
            **board_context(request, "items", current_region(request)),
            "item": item,
            "is_owner": request.user.is_authenticated and request.user.pk == item.owner_id,
            "my_request": my_request,
            "requests_for_owner": requests_for_owner,
            "item_region": REGION_LABELS.get(item.region, ""),
            "message_max": MESSAGE_MAX_LENGTH,
            "login_url": login_url(request),
        },
    )


def start_talk(request, *, item=None, notice=None):
    """2人だけのやりとりを始める (最初のメッセージつき)。すでにあればそれを返す。"""

    subject = item or notice
    body = (request.POST.get("body") or "").strip()[:MESSAGE_MAX_LENGTH]
    if not body:
        return None, "ひとことメッセージを書いてください。"

    with transaction.atomic():
        talk_request, created = ItemRequest.objects.get_or_create(
            item=item,
            notice=notice,
            requester=request.user,
            defaults={"nickname": user_nickname(request.user)},
        )
        if created:
            Message.objects.create(request=talk_request, sender=request.user, body=body)
            now = timezone.now()
            ItemRequest.objects.filter(pk=talk_request.pk).update(last_message_at=now, requester_read_at=now)
            word = item.request_word if item else "問い合わせ"
            notify(
                subject.owner,
                Notification.Kind.TALK,
                f"「{short(subject.title, 24)}」に「{word}」が届きました",
                reverse("chiebukuro:talk", args=[talk_request.pk]),
                actor=request.user,
            )
    return talk_request, ""


@board_open
@require_POST
@login_required
def item_request(request, pk):
    """「ほしい」「ゆずれます」「借りたい」「貸せます」+ ひとこと"""

    item = get_object_or_404(Item, pk=pk, status=Status.PUBLISHED)

    if item.owner_id == request.user.pk:
        return redirect("chiebukuro:item", pk=pk)

    existing = item.requests.filter(requester=request.user).first()
    if existing:
        return redirect("chiebukuro:talk", pk=existing.pk)

    if item.state != Item.State.OPEN:
        messages.error(request, "この書き込みは、もう相手が決まっています。")
        return redirect("chiebukuro:item", pk=pk)

    talk_request, error = start_talk(request, item=item)
    if error:
        messages.error(request, error)
        return redirect("chiebukuro:item", pk=pk)

    messages.success(request, f"「{item.request_word}」を送りました。返事が来たら🔔でお知らせします。")
    return redirect("chiebukuro:talk", pk=talk_request.pk)


@board_open
@require_POST
@login_required
def item_state(request, pk):
    """出した人が状態を変える (受付中に戻す・おわりにする)・取り下げる"""

    item = get_object_or_404(Item, pk=pk, owner=request.user)

    if request.POST.get("delete") == "yes":
        item.status = Status.HIDDEN
        item.save(update_fields=["status", "updated_at"])
        messages.success(request, "書き込みを取り下げました。")
        return redirect("chiebukuro:items")

    state = request.POST.get("state", "")
    if state in Item.State.values:
        item.state = state
        item.save(update_fields=["state", "updated_at"])
        if state == Item.State.OPEN:
            item.requests.update(is_chosen=False)
        messages.success(request, f"「{item.state_label()}」にしました。")

    return redirect("chiebukuro:item", pk=pk)


# =========================================================
# 募集・告知
# =========================================================

NOTICE_FILTERS = {
    "": "すべて",
    "shop": "お店・サービス",
    "lesson": "教室",
    "event": "イベント",
    "friends": "仲間・その他",
    "sitter": "シッター",
}


@board_open
def notice_list(request):

    region = current_region(request)
    kind = request.GET.get("kind", "")
    if kind not in NOTICE_FILTERS:
        kind = ""

    notices = by_region(active_notices(), region)
    if kind == "sitter":
        notices = notices.filter(kind__in=Notice.SITTER_KINDS)
    elif kind == "friends":
        notices = notices.filter(kind__in=["friends", "other"])
    elif kind:
        notices = notices.filter(kind=kind)

    page = Paginator(notices.order_by("-created_at"), PER_PAGE).get_page(request.GET.get("page"))

    return render(
        request,
        "chiebukuro/notices.html",
        {
            **board_context(request, "notices", region),
            "page": page,
            "kind": kind,
            "filters": NOTICE_FILTERS,
        },
    )


@board_open
@login_required
def notice_new(request):

    mine = active_notices().filter(owner=request.user).first()
    if mine:
        messages.info(request, f"募集・告知は1人1件までです。いまの告知は、あと{mine.days_left}日で終わります（取り下げると、すぐに新しく出せます）。")
        return redirect("chiebukuro:notice", pk=mine.pk)

    error = ""
    kind = clean_choice(request.GET.get("kind", ""), Notice.Kind.choices)
    values = {"kind": kind, "title": "", "body": "", "notice_region": current_region(request), "place": "", "event_date": "", "link": ""}

    if request.method == "POST":
        values = {
            "kind": clean_choice(request.POST.get("kind", ""), Notice.Kind.choices),
            "title": (request.POST.get("title") or "").strip(),
            "body": (request.POST.get("body") or "").strip(),
            "notice_region": clean_choice(request.POST.get("notice_region", ""), BOARD_REGION_CHOICES),
            "place": (request.POST.get("place") or "").strip()[:80],
            "event_date": (request.POST.get("event_date") or "").strip(),
            "link": (request.POST.get("link") or "").strip()[:500],
        }
        event_date = None
        if values["event_date"]:
            try:
                event_date = date.fromisoformat(values["event_date"])
            except ValueError:
                error = "日にちの形が正しくありません。"

        if error:
            pass
        elif not values["kind"]:
            error = "種類を選んでください。"
        elif not values["title"]:
            error = "タイトルを入力してください。"
        elif len(values["title"]) > ITEM_TITLE_MAX_LENGTH:
            error = f"タイトルは{ITEM_TITLE_MAX_LENGTH}文字までです。"
        elif not values["body"]:
            error = "内容を入力してください。"
        elif len(values["body"]) > NOTICE_BODY_MAX_LENGTH:
            error = f"内容は{NOTICE_BODY_MAX_LENGTH}文字までです。"
        elif values["link"] and not values["link"].startswith(("https://", "http://")):
            error = "リンクは https:// から始まるURLを入れてください。"
        elif request.POST.get("agree") != "yes":
            error = "ルールを確認して、チェックを入れてください。"
        else:
            notice = Notice.objects.create(
                kind=values["kind"],
                title=values["title"],
                body=values["body"],
                region=values["notice_region"],
                place=values["place"],
                event_date=event_date,
                link=values["link"],
                owner=request.user,
                nickname=user_nickname(request.user),
            )
            notify_staff(request, "新しい募集・告知", notice.title, reverse("admin:chiebukuro_notice_change", args=[notice.pk]))
            messages.success(request, f"告知を出しました。{Notice.DAYS}日間のせます。")
            return redirect("chiebukuro:notice", pk=notice.pk)

    return render(
        request,
        "chiebukuro/notice_form.html",
        {
            **board_context(request, "notices", current_region(request)),
            "values": values,
            "kinds": Notice.Kind.choices,
            "error": error,
            "title_max": ITEM_TITLE_MAX_LENGTH,
            "body_max": NOTICE_BODY_MAX_LENGTH,
            "days": Notice.DAYS,
        },
    )


@board_open
def notice_detail(request, pk):

    notice = get_object_or_404(Notice.objects.select_related("owner"), pk=pk)
    is_owner = request.user.is_authenticated and request.user.pk == notice.owner_id
    if notice.status != Status.PUBLISHED and not request.user.is_staff and not is_owner:
        raise Http404

    my_request = None
    inquiries = []
    if request.user.is_authenticated:
        if is_owner:
            inquiries = list(notice.requests.order_by("-last_message_at"))
        else:
            my_request = notice.requests.filter(requester=request.user).first()

    return render(
        request,
        "chiebukuro/notice.html",
        {
            **board_context(request, "notices", current_region(request)),
            "notice": notice,
            "is_owner": is_owner,
            "my_request": my_request,
            "inquiries": inquiries,
            "notice_region": REGION_LABELS.get(notice.region, ""),
            "message_max": MESSAGE_MAX_LENGTH,
            "login_url": login_url(request),
        },
    )


@board_open
@require_POST
@login_required
def notice_request(request, pk):
    """告知への問い合わせ (2人だけのやりとり)"""

    notice = get_object_or_404(Notice, pk=pk, status=Status.PUBLISHED)
    if notice.owner_id == request.user.pk:
        return redirect("chiebukuro:notice", pk=pk)
    existing = notice.requests.filter(requester=request.user).first()
    if existing:
        return redirect("chiebukuro:talk", pk=existing.pk)
    if not notice.is_active:
        messages.error(request, "この告知は、もう終わっています。")
        return redirect("chiebukuro:notice", pk=pk)

    talk_request, error = start_talk(request, notice=notice)
    if error:
        messages.error(request, error)
        return redirect("chiebukuro:notice", pk=pk)
    messages.success(request, "問い合わせを送りました。返事が来たら🔔でお知らせします。")
    return redirect("chiebukuro:talk", pk=talk_request.pk)


@board_open
@require_POST
@login_required
def notice_withdraw(request, pk):

    notice = get_object_or_404(Notice, pk=pk, owner=request.user)
    notice.status = Status.HIDDEN
    notice.save(update_fields=["status", "updated_at"])
    messages.success(request, "告知を取り下げました。")
    return redirect("chiebukuro:notices")


# =========================================================
# 2人だけのやりとり
# =========================================================

@board_open
@login_required
def talk(request, pk):

    talk_request = get_object_or_404(ItemRequest.objects.select_related("item", "notice", "requester"), pk=pk)
    if not talk_request.is_member(request.user):
        raise Http404

    is_owner = request.user.pk == talk_request.owner_id
    subject = talk_request.subject

    if request.method == "POST":
        body = (request.POST.get("body") or "").strip()[:MESSAGE_MAX_LENGTH]
        if body:
            last = talk_request.messages.order_by("-created_at").first()
            if not (last and last.sender_id == request.user.pk and last.body == body):
                Message.objects.create(request=talk_request, sender=request.user, body=body)
                talk_request.last_message_at = timezone.now()
                talk_request.save(update_fields=["last_message_at"])
                other = talk_request.requester if is_owner else subject.owner
                notify(
                    other,
                    Notification.Kind.TALK,
                    f"「{short(subject.title, 24)}」のやりとりに、新しいメッセージ",
                    reverse("chiebukuro:talk", args=[pk]) + "#bottom",
                    actor=request.user,
                )
        return redirect(reverse("chiebukuro:talk", args=[pk]) + "#bottom")

    # 読んだ印 (このやりとりのお知らせも既読に)
    field = "owner_read_at" if is_owner else "requester_read_at"
    setattr(talk_request, field, timezone.now())
    talk_request.save(update_fields=[field])
    Notification.objects.filter(
        user=request.user, read_at__isnull=True, url__startswith=reverse("chiebukuro:talk", args=[pk])
    ).update(read_at=timezone.now())

    return render(
        request,
        "chiebukuro/talk.html",
        {
            **board_context(request, "me"),
            "talk": talk_request,
            "subject": subject,
            "item": talk_request.item,
            "notice": talk_request.notice,
            "is_owner": is_owner,
            "other_name": talk_request.other_name(request.user),
            "talk_messages": talk_request.messages.all(),
            "message_max": MESSAGE_MAX_LENGTH,
        },
    )


@board_open
@require_POST
@login_required
def talk_choose(request, pk):
    """品物を出した人が「この人に決める」"""

    talk_request = get_object_or_404(ItemRequest.objects.select_related("item"), pk=pk, item__owner=request.user)
    item = talk_request.item

    with transaction.atomic():
        item.requests.update(is_chosen=False)
        item.state = Item.State.RESERVED
        item.save(update_fields=["state", "updated_at"])
        Message.objects.create(
            request=talk_request,
            sender=request.user,
            body=f"（{talk_request.display_name}さんに{item.deal_word}ことに決めました。受け渡しの日時と場所を決めましょう）",
        )
        talk_request.is_chosen = True
        talk_request.last_message_at = timezone.now()
        talk_request.save(update_fields=["is_chosen", "last_message_at"])
        notify(
            talk_request.requester,
            Notification.Kind.CHOSEN,
            f"「{short(item.title, 24)}」の相手に決まりました",
            reverse("chiebukuro:talk", args=[pk]) + "#bottom",
            actor=request.user,
        )

    messages.success(request, f"{talk_request.display_name}さんに決めました。")
    return redirect("chiebukuro:talk", pk=pk)


# =========================================================
# お知らせ・マイページ・プロフィール
# =========================================================

@board_open
@login_required
def notifications(request):

    rows = list(Notification.objects.filter(user=request.user)[:60])
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())

    return render(
        request,
        "chiebukuro/notifications.html",
        {**board_context(request, "bell"), "rows": rows, "unread": 0},
    )


@board_open
@login_required
def my_page(request):

    user = request.user
    talks = list(my_talks(user))
    for talk_request in talks:
        talk_request.unread = talk_request.unread_for(user)
        talk_request.other = talk_request.other_name(user)
        talk_request.mine = talk_request.owner_id == user.pk

    my_questions = (
        Question.objects.filter(author=user, status=Status.PUBLISHED)
        .annotate(answer_total=Count("answers", filter=Q(answers__status=Status.PUBLISHED)))
        .order_by("-created_at")[:30]
    )
    wanted = (
        Question.objects.filter(interests__user=user, status=Status.PUBLISHED)
        .annotate(answer_total=Count("answers", filter=Q(answers__status=Status.PUBLISHED)))
        .order_by("-last_answered_at")[:30]
    )
    board_profile = BoardProfile.objects.filter(user=user).first()

    return render(
        request,
        "chiebukuro/me.html",
        {
            **board_context(request, "me"),
            "talks": talks,
            "my_questions": my_questions,
            "wanted": wanted,
            "my_items": Item.objects.filter(owner=user).exclude(status=Status.HIDDEN).order_by("-created_at")[:30],
            "my_notices": Notice.objects.filter(owner=user, status=Status.PUBLISHED).order_by("-created_at")[:5],
            "home_region": REGION_LABELS.get(board_profile.region, "") if board_profile else "",
            "intro": board_profile.intro if board_profile else "",
            "nickname": user_nickname(user),
        },
    )


@board_open
@login_required
def profile_edit(request):

    from travel.models import UserProfile

    board_profile, _ = BoardProfile.objects.get_or_create(user=request.user)
    yapp_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    error = ""
    nickname = user_nickname(request.user)

    if request.method == "POST":
        nickname = (request.POST.get("nickname") or "").strip()
        intro = (request.POST.get("intro") or "").strip()
        board_profile.region = clean_choice(request.POST.get("home_region", ""), BOARD_REGION_CHOICES)
        board_profile.intro = intro
        if not nickname:
            error = "ニックネームを入力してください。"
        elif len(nickname) > 30:
            error = "ニックネームは30文字までです。"
        elif len(intro) > 160:
            error = "ひとことは160文字までです。"
        else:
            yapp_profile.nickname = nickname
            yapp_profile.save(update_fields=["nickname"])
            board_profile.save()
            messages.success(request, "プロフィールを保存しました。")
            return redirect("chiebukuro:profile", username=request.user.username)

    return render(
        request,
        "chiebukuro/profile_edit.html",
        {
            **board_context(request, "me"),
            "nickname": nickname,
            "board_profile": board_profile,
            "error": error,
        },
    )


@board_open
def profile(request, username):

    person = get_object_or_404(get_user_model(), username=username, is_active=True)
    show = request.GET.get("show", "posts")
    if show not in ("posts", "answers", "questions", "items"):
        show = "posts"

    posts = mark_liked(list(
        annotate_posts(Post.objects.filter(author=person, status=Status.PUBLISHED)).order_by("-created_at")[:30]
    ), request.user)
    answers = list(
        Answer.objects.filter(author=person, status=Status.PUBLISHED, question__status=Status.PUBLISHED)
        .select_related("question").order_by("-created_at")[:30]
    )
    questions = list(
        Question.objects.filter(author=person, status=Status.PUBLISHED)
        .annotate(answer_total=Count("answers", filter=Q(answers__status=Status.PUBLISHED)))
        .order_by("-created_at")[:30]
    )
    items = list(Item.objects.filter(owner=person, status=Status.PUBLISHED).exclude(state=Item.State.DONE)[:30])
    helpful = (
        Thanks.objects.filter(answer__author=person).count()
        + PostLike.objects.filter(post__author=person).count()
    )
    board_profile = BoardProfile.objects.filter(user=person).first()

    return render(
        request,
        "chiebukuro/profile.html",
        {
            **board_context(request, "me" if person == request.user else "profile"),
            "person": person,
            "nickname": user_nickname(person),
            "home_region": REGION_LABELS.get(board_profile.region, "") if board_profile else "",
            "intro": board_profile.intro if board_profile else "",
            "posts": posts,
            "answers": answers,
            "questions": questions,
            "items": items,
            "helpful": helpful,
            "show": show,
            "is_me": person == request.user,
        },
    )


# =========================================================
# 検索 (掲示板ぜんぶ)
# =========================================================

@board_open
def search(request):

    query = (request.GET.get("q") or "").strip()[:60]
    results = {}
    if query:
        results["questions"] = best_answers(list(question_list(query=query)[:10]))
        results["posts"] = mark_liked(list(
            annotate_posts(Post.objects.filter(status=Status.PUBLISHED, body__icontains=query)).order_by("-created_at")[:10]
        ), request.user)
        results["items"] = list(
            open_items().filter(Q(title__icontains=query) | Q(body__icontains=query)).order_by("-created_at")[:10]
        )
        results["notices"] = list(
            active_notices().filter(Q(title__icontains=query) | Q(body__icontains=query)).order_by("-created_at")[:10]
        )

    return render(
        request,
        "chiebukuro/search.html",
        {
            **board_context(request, "search"),
            "query": query,
            "results": results,
            "found": any(results.values()) if results else False,
        },
    )


@board_open
@require_POST
@login_required
def report(request):

    target = request.POST.get("target", "")
    target_id = request.POST.get("target_id", "")
    if target in ("question", "answer", "item", "post", "notice") and target_id.isdigit():
        Report.objects.create(
            target=target,
            target_id=int(target_id),
            reason=(request.POST.get("reason") or "").strip()[:500],
            reporter=request.user,
        )
        notify_staff(request, "通報", f"{target} #{target_id}", reverse("admin:chiebukuro_report_changelist"))
        messages.success(request, "運営に知らせました。確認します。ありがとうございます。")
    return redirect(safe_next(request, reverse("chiebukuro:home")))


def notify_staff(request, subject, text, admin_path):
    """運営にメールで知らせる (事前アンケートと同じ仕組み・送り先)"""

    import threading

    from django.conf import settings

    from pre_survey.alerts import _send

    recipient = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", "")
    if not recipient:
        return
    body = f"{text}\n\n{request.build_absolute_uri(admin_path)}\n"
    threading.Thread(target=_send, args=(f"[知恵袋] {subject}", body, recipient), daemon=True).start()
