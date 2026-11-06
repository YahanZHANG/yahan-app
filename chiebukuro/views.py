"""
スイス生活の知恵袋 (掲示板) の画面。

読むのはだれでも (公開前は運営だけ)。書く・押すにはログインが必要。
"""

import logging
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    BOARD_REGION_CHOICES,
    THEME_CHOICES,
    Answer,
    BoardSettings,
    Interest,
    Item,
    ItemRequest,
    Message,
    Post,
    PostLike,
    PostReply,
    Question,
    Report,
    Status,
    Thanks,
)
from .services import (
    attach_previews,
    popular_questions,
    question_list,
    timeline,
    user_nickname,
    waiting_questions,
)


logger = logging.getLogger(__name__)

QUESTION_MAX_LENGTH = 200
ANSWER_MAX_LENGTH = 2000
MESSAGE_MAX_LENGTH = 1000
ITEM_TITLE_MAX_LENGTH = 80
ITEM_BODY_MAX_LENGTH = 1000
PER_PAGE = 20

THEME_LABELS = dict(THEME_CHOICES)
REGION_LABELS = dict(BOARD_REGION_CHOICES)

# HOME のテーマの並び (「その他」は最後)
THEME_ORDER = [value for value, _ in THEME_CHOICES if value != "other"] + ["other"]

THEME_EMOJI = {
    "life": "🏠",
    "shopping": "🛒",
    "childcare": "👶",
    "work": "💼",
    "language": "🗣️",
    "outing": "⛰️",
    "health": "💆",
    "money": "💰",
    "culture": "🤝",
    "other": "💬",
}


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


def board_context(request, tab):
    context = {
        "tab": tab,
        "board_is_open": BoardSettings.current().is_open,
        "unread_talks": 0,
    }
    if request.user.is_authenticated:
        context["unread_talks"] = sum(
            1 for talk in my_talks(request.user) if talk.unread_for(request.user)
        )
    return context


def my_talks(user):
    return (
        ItemRequest.objects
        .filter(Q(requester=user) | Q(item__owner=user))
        .select_related("item")
        .order_by("-last_message_at")
    )


def clean_choice(value, choices):
    return value if value in dict(choices) else ""


def login_url(request):
    return f"{reverse('login')}?next={request.get_full_path()}"


def upload_board_photo(uploaded_file):
    """写真を小さくして Cloudinary に保存 (和食・おでかけと同じ仕組み)"""

    from outings.services.user_event_cloudinary import upload_user_event_photo
    from outings.services.user_event_images import process_user_event_image

    processed = process_user_event_image(uploaded_file, max_size=1200, quality=78)
    return upload_user_event_photo(processed, folder="yapp/board/items", filename="photo.webp")


# =========================================================
# HOME (質問の一覧)
# =========================================================

HOME_TABS = {
    "popular": "人気",
    "new": "新着",
    "waiting": "答え待ち",
}


@board_open
def home(request):

    tab = request.GET.get("tab", "popular")
    if tab not in HOME_TABS:
        tab = "popular"
    theme = clean_choice(request.GET.get("theme", ""), THEME_CHOICES)
    region = clean_choice(request.GET.get("region", ""), BOARD_REGION_CHOICES)
    query = (request.GET.get("q") or "").strip()[:60]

    rows = []
    questions = []
    if tab == "new":
        rows = timeline(theme, region, query, limit=40)
    elif tab == "waiting":
        questions = waiting_questions(theme, region, query, limit=40)
    else:
        questions = popular_questions(theme, region, query, limit=20)

    # キーワード検索では、質問の一覧 (答えのちら見せ付き) も出す
    search_page = None
    if query:
        search_page = Paginator(question_list(theme, region, "new", query), PER_PAGE).get_page(request.GET.get("page"))
        attach_previews(search_page.object_list)

    counts = dict(
        Question.objects.filter(status=Status.PUBLISHED)
        .values("theme").annotate(n=Count("pk")).values_list("theme", "n")
    )
    themes = [
        {"value": value, "label": THEME_LABELS[value], "emoji": THEME_EMOJI.get(value, "")}
        for value in THEME_ORDER
        if counts.get(value)
    ]

    totals = {
        "questions": Question.objects.filter(status=Status.PUBLISHED).count(),
        "answers": Answer.objects.filter(status=Status.PUBLISHED, question__status=Status.PUBLISHED).count(),
    }

    return render(
        request,
        "chiebukuro/home.html",
        {
            **board_context(request, "questions"),
            "home_tab": tab,
            "home_tabs": HOME_TABS,
            "rows": rows,
            "questions": questions,
            "search_page": search_page,
            "themes": themes,
            "theme": theme,
            "theme_label": THEME_LABELS.get(theme, ""),
            "region": region,
            "region_label": REGION_LABELS.get(region, ""),
            "regions": BOARD_REGION_CHOICES,
            "query": query,
            "totals": totals,
            "theme_emoji": THEME_EMOJI,
            "post_max": POST_MAX_LENGTH,
        },
    )


# =========================================================
# つぶやき
# =========================================================

POST_MAX_LENGTH = 500


@board_open
@login_required
def post_new(request):

    error = ""
    body = (request.POST.get("body") or "").strip() if request.method == "POST" else ""
    theme = clean_choice(request.POST.get("theme", "") if request.method == "POST" else request.GET.get("theme", ""), THEME_CHOICES)
    region = clean_choice(request.POST.get("region", ""), BOARD_REGION_CHOICES)

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
            messages.success(request, "つぶやきました！")
            return redirect(reverse("chiebukuro:home") + "?tab=new")

    return render(
        request,
        "chiebukuro/post_form.html",
        {
            **board_context(request, "questions"),
            "body": body,
            "theme": theme,
            "region": region,
            "themes": [(value, THEME_LABELS[value], THEME_EMOJI.get(value, "")) for value in THEME_ORDER],
            "regions": BOARD_REGION_CHOICES,
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
        return redirect(reverse("chiebukuro:post", args=[pk]) + "#replies")

    liked = request.user.is_authenticated and post.likes.filter(user=request.user).exists()

    return render(
        request,
        "chiebukuro/post.html",
        {
            **board_context(request, "questions"),
            "post": post,
            "replies": post.replies.filter(status=Status.PUBLISHED),
            "like_total": post.likes.count(),
            "liked": liked,
            "theme_label": THEME_LABELS.get(post.theme, ""),
            "region_label": REGION_LABELS.get(post.region, ""),
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
    return redirect(request.POST.get("next") or reverse("chiebukuro:post", args=[pk]))


@board_open
@require_POST
@login_required
def delete_post(request, pk):

    post = get_object_or_404(Post, pk=pk, author=request.user)
    post.status = Status.HIDDEN
    post.save(update_fields=["status"])
    messages.success(request, "つぶやきを消しました。")
    return redirect(reverse("chiebukuro:home") + "?tab=new")


@board_open
def new_choice(request):
    """真ん中の「＋」: 何を書くか選ぶ"""

    return render(request, "chiebukuro/new.html", board_context(request, "new"))


# =========================================================
# プロフィール
# =========================================================

@board_open
def profile(request, username):

    from django.contrib.auth import get_user_model

    person = get_object_or_404(get_user_model(), username=username, is_active=True)
    posts = list(
        Post.objects.filter(author=person, status=Status.PUBLISHED)
        .annotate(reply_total=Count("replies", distinct=True), like_total=Count("likes", distinct=True))
        .order_by("-created_at")[:30]
    )
    answers = list(
        Answer.objects.filter(author=person, status=Status.PUBLISHED, question__status=Status.PUBLISHED)
        .select_related("question").order_by("-created_at")[:30]
    )
    questions = list(Question.objects.filter(author=person, status=Status.PUBLISHED).order_by("-created_at")[:30])
    helpful = (
        Thanks.objects.filter(answer__author=person).count()
        + PostLike.objects.filter(post__author=person).count()
    )

    return render(
        request,
        "chiebukuro/profile.html",
        {
            **board_context(request, "me" if person == request.user else "questions"),
            "person": person,
            "nickname": user_nickname(person),
            "posts": posts,
            "answers": answers,
            "questions": questions,
            "helpful": helpful,
            "is_me": person == request.user,
        },
    )


# =========================================================
# 質問と答え
# =========================================================

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
            messages.success(request, "答えを書き込みました。ありがとうございます！")
            return redirect(reverse("chiebukuro:question", args=[question.pk]) + "#answers")

    # 参考になった数の多い順 (同じなら古い順)。いちばん上を「いちばん参考になった」として大きく出す
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

    interest_total = question.interests.count() + question.survey_interest_count

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
            **board_context(request, "questions"),
            "question": question,
            "theme_label": THEME_LABELS.get(question.theme, ""),
            "theme_emoji": THEME_EMOJI.get(question.theme, ""),
            "region_label": REGION_LABELS.get(question.region, ""),
            "answers": answers,
            "best_answer": best_answer,
            "thanked": thanked,
            "interested": interested,
            "interest_total": interest_total,
            "error": error,
            "draft": draft,
            "max_length": ANSWER_MAX_LENGTH,
            "related": related,
            "login_url": login_url(request),
        },
    )


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
        region = clean_choice(request.POST.get("region", ""), BOARD_REGION_CHOICES)

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
            messages.success(request, "質問を書き込みました。答えがついたら、マイページで見られます。")
            return redirect("chiebukuro:question", pk=question.pk)

    return render(
        request,
        "chiebukuro/ask.html",
        {
            **board_context(request, "questions"),
            "body": body,
            "theme": theme,
            "region": region,
            "themes": [(value, THEME_LABELS[value], THEME_EMOJI.get(value, "")) for value in THEME_ORDER],
            "regions": BOARD_REGION_CHOICES,
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
    return redirect(reverse("chiebukuro:question", args=[pk]))


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
# ゆずります・本の貸し借り
# =========================================================

ITEM_TABS = {
    Item.Kind.GIVE: "give",
    Item.Kind.BOOK: "books",
}


@board_open
def item_list(request, kind):

    region = clean_choice(request.GET.get("region", ""), BOARD_REGION_CHOICES)
    show_done = request.GET.get("all") == "1"

    items = Item.objects.filter(kind=kind, status=Status.PUBLISHED)
    if region:
        items = items.filter(Q(region=region) | Q(region=""))
    if not show_done:
        items = items.exclude(state=Item.State.DONE)
    items = items.annotate(request_total=Count("requests")).order_by("-created_at")

    page = Paginator(items, PER_PAGE).get_page(request.GET.get("page"))

    return render(
        request,
        "chiebukuro/items.html",
        {
            **board_context(request, ITEM_TABS[kind]),
            "kind": kind,
            "kind_label": Item.Kind(kind).label,
            "page": page,
            "region": region,
            "regions": BOARD_REGION_CHOICES,
            "show_done": show_done,
        },
    )


@board_open
@login_required
def item_new(request, kind):

    if kind not in Item.Kind.values:
        raise Http404

    error = ""
    values = {"title": "", "body": "", "region": "", "place": ""}

    if request.method == "POST":
        values = {
            "title": (request.POST.get("title") or "").strip(),
            "body": (request.POST.get("body") or "").strip(),
            "region": clean_choice(request.POST.get("region", ""), BOARD_REGION_CHOICES),
            "place": (request.POST.get("place") or "").strip()[:80],
        }
        photo = request.FILES.get("photo")

        if not values["title"]:
            error = "品物の名前を入力してください。" if kind == Item.Kind.GIVE else "本のタイトルを入力してください。"
        elif len(values["title"]) > ITEM_TITLE_MAX_LENGTH:
            error = f"名前は{ITEM_TITLE_MAX_LENGTH}文字までです。"
        elif len(values["body"]) > ITEM_BODY_MAX_LENGTH:
            error = f"説明は{ITEM_BODY_MAX_LENGTH}文字までです。"
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
                    owner=request.user,
                    nickname=user_nickname(request.user),
                    photo_url=photo_url,
                    **values,
                )
                notify_staff(request, f"新しい{item.get_kind_display()}", item.title, reverse("admin:chiebukuro_item_change", args=[item.pk]))
                messages.success(request, "書き込みました。「ほしい」「借りたい」が届いたら、マイページに出ます。")
                return redirect("chiebukuro:item", pk=item.pk)

    return render(
        request,
        "chiebukuro/item_form.html",
        {
            **board_context(request, ITEM_TABS[kind]),
            "kind": kind,
            "kind_label": Item.Kind(kind).label,
            "values": values,
            "regions": BOARD_REGION_CHOICES,
            "error": error,
            "title_max": ITEM_TITLE_MAX_LENGTH,
            "body_max": ITEM_BODY_MAX_LENGTH,
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
            **board_context(request, ITEM_TABS[item.kind]),
            "item": item,
            "is_owner": request.user.is_authenticated and request.user.pk == item.owner_id,
            "my_request": my_request,
            "requests_for_owner": requests_for_owner,
            "region_label": REGION_LABELS.get(item.region, ""),
            "message_max": MESSAGE_MAX_LENGTH,
            "login_url": login_url(request),
        },
    )


@board_open
@require_POST
@login_required
def item_request(request, pk):
    """「ほしい」「借りたい」+ ひとこと。出した人との2人だけのやりとりが始まる。"""

    item = get_object_or_404(Item, pk=pk, status=Status.PUBLISHED)

    if item.owner_id == request.user.pk:
        return redirect("chiebukuro:item", pk=pk)

    existing = item.requests.filter(requester=request.user).first()
    if existing:
        return redirect("chiebukuro:talk", pk=existing.pk)

    if item.state != Item.State.OPEN:
        messages.error(request, "この品物は、もう相手が決まっています。")
        return redirect("chiebukuro:item", pk=pk)

    body = (request.POST.get("body") or "").strip()[:MESSAGE_MAX_LENGTH]
    if not body:
        messages.error(request, "ひとことメッセージを書いてください。")
        return redirect("chiebukuro:item", pk=pk)

    with transaction.atomic():
        talk_request, created = ItemRequest.objects.get_or_create(
            item=item,
            requester=request.user,
            defaults={"nickname": user_nickname(request.user)},
        )
        if created:
            Message.objects.create(request=talk_request, sender=request.user, body=body)
            now = timezone.now()
            ItemRequest.objects.filter(pk=talk_request.pk).update(last_message_at=now, requester_read_at=now)

    messages.success(request, f"「{item.request_word}」を送りました。返事はマイページの「やりとり」に届きます。")
    return redirect("chiebukuro:talk", pk=talk_request.pk)


@board_open
@require_POST
@login_required
def item_state(request, pk):
    """出した人が状態を変える (受付中に戻す・おわりにする・返してもらった)"""

    item = get_object_or_404(Item, pk=pk, owner=request.user)
    state = request.POST.get("state", "")

    if state in Item.State.values:
        item.state = state
        item.save(update_fields=["state", "updated_at"])
        if state == Item.State.OPEN:
            item.requests.update(is_chosen=False)
        messages.success(request, f"「{item.state_label()}」にしました。")

    if request.POST.get("delete") == "yes":
        item.status = Status.HIDDEN
        item.save(update_fields=["status", "updated_at"])
        messages.success(request, "書き込みを取り下げました。")
        return redirect(f"chiebukuro:{ITEM_TABS[item.kind]}")

    return redirect("chiebukuro:item", pk=pk)


@board_open
@login_required
def talk(request, pk):
    """出した人と、ほしい・借りたい人の2人だけのやりとり"""

    talk_request = get_object_or_404(ItemRequest.objects.select_related("item", "requester"), pk=pk)
    if not talk_request.is_member(request.user):
        raise Http404

    is_owner = request.user.pk == talk_request.item.owner_id

    if request.method == "POST":
        body = (request.POST.get("body") or "").strip()[:MESSAGE_MAX_LENGTH]
        if body:
            last = talk_request.messages.order_by("-created_at").first()
            if not (last and last.sender_id == request.user.pk and last.body == body):
                Message.objects.create(request=talk_request, sender=request.user, body=body)
                talk_request.last_message_at = timezone.now()
                talk_request.save(update_fields=["last_message_at"])
        return redirect(reverse("chiebukuro:talk", args=[pk]) + "#bottom")

    # 読んだ印
    field = "owner_read_at" if is_owner else "requester_read_at"
    setattr(talk_request, field, timezone.now())
    talk_request.save(update_fields=[field])

    return render(
        request,
        "chiebukuro/talk.html",
        {
            **board_context(request, "me"),
            "talk": talk_request,
            "item": talk_request.item,
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
    """出した人が「この人にゆずる・貸す」と決める"""

    talk_request = get_object_or_404(ItemRequest.objects.select_related("item"), pk=pk, item__owner=request.user)
    item = talk_request.item

    with transaction.atomic():
        item.requests.update(is_chosen=False)
        talk_request.is_chosen = True
        talk_request.save(update_fields=["is_chosen"])
        item.state = Item.State.RESERVED
        item.save(update_fields=["state", "updated_at"])
        word = "貸す" if item.kind == Item.Kind.BOOK else "ゆずる"
        Message.objects.create(
            request=talk_request,
            sender=request.user,
            body=f"（{talk_request.display_name}さんに{word}ことに決めました。受け渡しの日時と場所を決めましょう）",
        )
        talk_request.last_message_at = timezone.now()
        talk_request.save(update_fields=["last_message_at"])

    messages.success(request, f"{talk_request.display_name}さんに決めました。")
    return redirect("chiebukuro:talk", pk=pk)


# =========================================================
# マイページ・通報
# =========================================================

@board_open
@login_required
def my_page(request):

    user = request.user
    talks = list(my_talks(user))
    for talk_request in talks:
        talk_request.unread = talk_request.unread_for(user)
        talk_request.other = talk_request.other_name(user)
        talk_request.mine = talk_request.item.owner_id == user.pk

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

    return render(
        request,
        "chiebukuro/me.html",
        {
            **board_context(request, "me"),
            "talks": talks,
            "my_questions": my_questions,
            "wanted": wanted,
            "my_items": Item.objects.filter(owner=user).exclude(status=Status.HIDDEN).order_by("-created_at")[:30],
            "answer_total": Answer.objects.filter(author=user, status=Status.PUBLISHED).count(),
            "nickname": user_nickname(user),
        },
    )


@board_open
@require_POST
@login_required
def report(request):

    target = request.POST.get("target", "")
    target_id = request.POST.get("target_id", "")
    if target in ("question", "answer", "item", "post") and target_id.isdigit():
        Report.objects.create(
            target=target,
            target_id=int(target_id),
            reason=(request.POST.get("reason") or "").strip()[:500],
            reporter=request.user,
        )
        notify_staff(request, "通報", f"{target} #{target_id}", reverse("admin:chiebukuro_report_changelist"))
        messages.success(request, "運営に知らせました。確認します。ありがとうございます。")
    return redirect(request.POST.get("next") or "chiebukuro:home")


def notify_staff(request, subject, text, admin_path):
    """運営にメールで知らせる (事前アンケートと同じ仕組み・送り先)"""

    from pre_survey.alerts import _send
    from django.conf import settings
    import threading

    recipient = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", "")
    if not recipient:
        return
    body = f"{text}\n\n{request.build_absolute_uri(admin_path)}\n"
    threading.Thread(target=_send, args=(f"[知恵袋] {subject}", body, recipient), daemon=True).start()
