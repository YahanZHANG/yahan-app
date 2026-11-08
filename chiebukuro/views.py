"""
スイス生活の知恵袋 (掲示板) の画面。

メニュー: HOME・つぶやき・質問・ゆずりあい・募集告知 (+ 右上に🔔とマイページ)
読むのはだれでも (公開前は運営だけ)。書く・押すにはログインが必要。
"""

import logging
from datetime import date
from functools import wraps

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import avatar as avatar_art
from .japan_calendar import JST as JAPAN_TZ
from .daily import today_card
from .japan_calendar import japan_holiday, moon_path, today_info
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
    STAMPS,
    Poll,
    PollChoice,
    PollVote,
    Post,
    PostReply,
    PushDevice,
    Question,
    Reaction,
    Report,
    Sponsor,
    Status,
    Thanks,
)
from .services import (
    attach_stamps,
    best_answers,
    current_sponsor,
    my_votes,
    poll_for_home,
    poll_result,
    weekend_outings,
    featured_this_week,
    give_items_with_photo,
    news_headlines,
    today_in_switzerland,
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
        if not can_preview(request):
            return render(request, "chiebukuro/closed.html", status=200)
        return view(request, *args, **kwargs)

    return wrapper


PREVIEW_SESSION_KEY = "chiebukuro_preview"


def can_preview(request):
    """
    公開中ならだれでも。公開前は、運営と、先行公開のリンク (?preview=鍵) を開いた人だけ。
    リンクの鍵はセッションに覚えるので、2回目からは鍵なしの URL でも見られる。
    """

    settings_row = BoardSettings.current()
    if settings_row.is_open or request.user.is_staff:
        return True
    key = settings_row.preview_key
    if not key:
        return False
    if request.GET.get("preview") == key:
        request.session[PREVIEW_SESSION_KEY] = key
    if request.session.get(PREVIEW_SESSION_KEY) == key:
        request.board_preview = True
        return True
    return False


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


def board_color(user):
    """着せかえの色。12時間ごとに変える設定なら、半日ごとに順番に"""

    if not user.is_authenticated:
        return "classic"
    row = BoardProfile.objects.filter(user=user).values("color", "color_auto").first()
    if not row:
        return "classic"
    if row["color_auto"]:
        now = timezone.localtime()
        colors = BoardProfile.Color.values
        return colors[(now.toordinal() * 2 + (1 if now.hour >= 12 else 0)) % len(colors)]
    return row["color"]


def board_context(request, tab, region=None):
    fab = FAB.get(tab)
    return {
        "board_color": board_color(request.user),
        "tab": tab,
        "board_is_open": BoardSettings.current().is_open,
        "board_preview": getattr(request, "board_preview", False),
        "unread": unread_notifications(request.user),
        "fab_label": fab[0] if fab else "",
        "fab_url": reverse(fab[1]) if fab else "",
        "region": region or "",
        "region_label": REGION_LABELS.get(region or "", ""),
        "regions": BOARD_REGION_CHOICES,
        "stamp_list": STAMPS,
        "needs_rules": needs_rules(request.user),
    }


def needs_rules(user):
    """
    書きこむ前に、ルールの同意画面を出すか。
    "first" = まだ同意していない / "updated" = 同意のあとにルールが変わった / "" = 不要
    """
    if not user.is_authenticated:
        return ""
    agreed_at = BoardProfile.objects.filter(user=user).values_list("rules_agreed_at", flat=True).first()
    if not agreed_at:
        return "first"
    updated_at = BoardSettings.current().rules_updated_at
    if updated_at and agreed_at < updated_at:
        return "updated"
    return ""


def my_talks(user):
    return (
        ItemRequest.objects
        .filter(Q(requester=user) | Q(item__owner=user) | Q(notice__owner=user))
        .select_related("item", "notice")
        .order_by("-last_message_at")
    )


def upload_board_photo(uploaded_file, folder="items"):
    """写真を小さくして Cloudinary に保存 (和食・おでかけと同じ仕組み)"""

    from outings.services.user_event_cloudinary import upload_user_event_photo
    from outings.services.user_event_images import process_user_event_image

    processed = process_user_event_image(uploaded_file, max_size=1200, quality=78)
    return upload_user_event_photo(processed, folder=f"yapp/board/{folder}", filename="photo.webp")


PHOTO_ERROR = "写真を保存できませんでした。写真なしで送るか、別の写真を選んでください。"


def take_photo(request, folder):
    """フォームの写真 (任意) を保存して (URL, エラー) を返す。写真がなければ ("", "")"""

    photo = request.FILES.get("photo")
    if not photo:
        return "", ""
    try:
        return upload_board_photo(photo, folder), ""
    except (ValidationError, Exception):
        logger.exception("board photo upload failed")
        return "", PHOTO_ERROR


def annotate_posts(queryset):
    return queryset.annotate(
        reply_total=Count("replies", filter=Q(replies__status=Status.PUBLISHED), distinct=True),
    )


def mark_liked(posts, user):
    """つぶやきに押されたスタンプを付ける"""
    return attach_stamps(posts, "post", user)


def active_notices():
    return Notice.objects.filter(status=Status.PUBLISHED, expires_at__gt=timezone.now())


def open_items():
    return Item.objects.filter(status=Status.PUBLISHED).exclude(state=Item.State.DONE)


# =========================================================
# HOME: 各コーナーの新しいものを少しずつ
# =========================================================

VOTER_COOKIE = "cb_voter"


@board_open
def home(request):
    """
    HOME: 個人のニーズにかかわらず、みんなの参考になるもの
    (アンケート・広告枠・今週末のおでかけ) と、掲示板の新着・答えを待っている質問。
    """

    import uuid

    region = current_region(request)
    voter_key = request.COOKIES.get(VOTER_COOKIE, "")
    season = BoardSettings.current().season(timezone.localdate())
    cal = today_info()
    poll = poll_for_home(request, voter_key)
    show_daily = True
    if request.user.is_authenticated:
        show_daily = BoardProfile.objects.filter(user=request.user, daily_popup=False).first() is None
    daily = today_card(timezone.localdate(), str(request.user.pk) if request.user.is_authenticated else voter_key)

    response = render(
        request,
        "chiebukuro/home.html",
        {
            **board_context(request, "home", region),
            "poll": poll,
            "daily": daily,
            "show_daily": show_daily,
            "sponsor": current_sponsor(),
            "outings": weekend_outings(limit=6),
            "featured": featured_this_week(),
            "gives": give_items_with_photo(region),
            "headlines": news_headlines(),
            "waiting": waiting_questions(region=region, limit=3),
            "today": timezone.localdate(),
            "hero_time": hero_time(),
            "hero_season": season,
            "cal": cal,
            "moon_art": moon_path(92, 44, 24, cal["lit"], cal["waxing"]),
            "moon_mini": moon_path(20, 20, 14, cal["lit"], cal["waxing"]),
            "japan_now": timezone.now().astimezone(JAPAN_TZ),
            "japan_holiday": japan_holiday(timezone.now().astimezone(JAPAN_TZ).date()),
            "season_label": SEASON_LABELS.get(season, ""),
        },
    )
    if not voter_key and not request.user.is_authenticated:
        response.set_cookie(VOTER_COOKIE, uuid.uuid4().hex, max_age=400 * 86400, samesite="Lax")
    return response


SEASON_LABELS = {
    "spring": "🌸 お花見の季節",
    "nationalday": "🇨🇭 8月1日は建国記念日",
    "halloween": "🎃 ハロウィン",
    "autumn": "🍁 紅葉の季節",
    "christmas": "🎄 アドベント",
    "newyear": "🎍 お正月",
}

SKY_BY_EMOJI = {"☀️": "clear", "🌤️": "partly", "⛅": "partly", "☁️": "cloudy", "🌫️": "cloudy",
                "🌦️": "rain", "🌧️": "rain", "⛈️": "rain", "🌨️": "snow", "❄️": "snow"}


def sky_for(weather):
    """HOME の景色の空: clear / cloudy / rain / snow"""
    return SKY_BY_EMOJI.get((weather or {}).get("emoji", ""), "clear")


def hero_time():
    """HOME の景色の時間: 朝 (6-9時)・昼・夕方 (16-18時、冬は早い)・夜"""
    hour = timezone.localtime().hour
    if 6 <= hour < 9:
        return "morning"
    if 9 <= hour < 16:
        return "day"
    if 16 <= hour < 18:
        return "evening"
    return "night"


def nearest_region(lat, lon):
    """現在地にいちばん近い地域 (天気を出す地域の中から)"""

    from news.services.info_bar import REGION_COORDS

    import math

    def distance(item):
        _, (rlat, rlon) = item
        return (rlat - lat) ** 2 + ((rlon - lon) * math.cos(math.radians(lat))) ** 2

    slug, coords = min(REGION_COORDS.items(), key=distance)
    # スイスの外 (だいたい 150km 以上離れている) なら使わない
    return slug if distance((slug, coords)) < 1.9 else ""


@board_open
def today_strip(request):
    """HOME の天気・為替。外のサービスに聞くので、ページとは別に読みこむ。
    ?lat=&lon= があれば (端末の現在地)、いちばん近い地域の天気"""

    region = current_region(request)
    here = ""
    try:
        lat, lon = float(request.GET["lat"]), float(request.GET["lon"])
        here = nearest_region(lat, lon)
    except (KeyError, ValueError):
        pass
    place_region = here or region
    info = today_in_switzerland(place_region)
    place = REGION_LABELS.get(place_region, "") or "チューリッヒ"
    return render(
        request,
        "chiebukuro/_today.html",
        {**info, "sky": sky_for(info.get("weather")), "place": place, "is_here": bool(here)},
    )


@login_required
@require_POST
def daily_off(request):
    """「今日のひとこと」をもう出さない (マイページの設定で戻せる)"""

    from django.http import JsonResponse

    BoardProfile.objects.update_or_create(user=request.user, defaults={"daily_popup": False})
    return JsonResponse({"ok": True})


@board_open
def fx_detail(request):
    """HOME の為替をタップしたとき: この30日の推移"""

    from .services import fx_history, sparkline

    history = fx_history()
    rows = []
    for code, label, unit, digits in (("JPY", "円", "円", 1), ("EUR", "ユーロ", "€", 3)):
        points = (history or {}).get(code) or []
        if len(points) < 2:
            continue
        first, last = points[0][1], points[-1][1]
        rows.append({
            "label": label, "unit": unit, "digits": digits,
            "line": sparkline(points),
            "first": first, "last": last, "since": "{}月{}日".format(*[int(part) for part in points[0][0].split("-")[1:]]),
            "change": round((last / first - 1) * 100, 1),
        })
    return render(request, "chiebukuro/_fx_detail.html", {"rows": rows})


@board_open
@require_POST
def poll_vote(request, pk):
    """アンケートに答える (ログインなしでも、ブラウザごとに1票)。答え直しもできる"""

    poll = get_object_or_404(Poll, pk=pk)
    choice = poll.choices.filter(pk=request.POST.get("choice") or 0).first()
    voter_key = request.COOKIES.get(VOTER_COOKIE, "")
    if choice and (request.user.is_authenticated or voter_key):
        votes = PollVote.objects.filter(poll=poll)
        votes = votes.filter(user=request.user) if request.user.is_authenticated else votes.filter(user__isnull=True, voter_key=voter_key)
        vote = votes.first()
        if vote:
            vote.choice = choice
            vote.save(update_fields=["choice"])
        else:
            PollVote.objects.create(
                poll=poll,
                choice=choice,
                user=request.user if request.user.is_authenticated else None,
                voter_key="" if request.user.is_authenticated else voter_key[:40],
            )
    return redirect(safe_next(request, reverse("chiebukuro:home")) + f"#poll{poll.pk}")


@board_open
def poll_list(request):

    voter_key = request.COOKIES.get(VOTER_COOKIE, "")
    polls = list(Poll.objects.prefetch_related("choices")[:30])
    mine = my_votes(request, voter_key, [poll.pk for poll in polls])
    for poll in polls:
        poll_result(poll, mine.get(poll.pk))
    return render(request, "chiebukuro/polls.html", {**board_context(request, "home"), "polls": polls})


def sponsor_click(request, pk):
    """広告のクリックを数えてから、広告主のページへ"""

    from django.db.models import F

    sponsor = get_object_or_404(Sponsor, pk=pk)
    Sponsor.objects.filter(pk=pk).update(clicks=F("clicks") + 1)
    return redirect(sponsor.link)


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
            photo_url, error = ("", "") if recent else take_photo(request, "posts")
        if not error:
            post = recent or Post.objects.create(
                body=body,
                theme=theme,
                region=region,
                photo_url=photo_url,
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
            photo_url, error = take_photo(request, "replies")
            if error:
                messages.error(request, error)
                return redirect(reverse("chiebukuro:post", args=[pk]) + "#replies")
            PostReply.objects.create(post=post, body=body, photo_url=photo_url, author=request.user, nickname=user_nickname(request.user))
            notify(
                post.author,
                Notification.Kind.REPLY,
                f"あなたのつぶやき「{short(post.body, 24)}」に返信がありました",
                reverse("chiebukuro:post", args=[pk]) + "#replies",
                actor=request.user,
            )
        return redirect(reverse("chiebukuro:post", args=[pk]) + "#replies")

    post.reply_total = post.replies.filter(status=Status.PUBLISHED).count()
    attach_stamps([post], "post", request.user)
    replies = attach_stamps(list(post.replies.filter(status=Status.PUBLISHED).select_related("author")), "reply", request.user)

    return render(
        request,
        "chiebukuro/post.html",
        {
            **board_context(request, "posts", current_region(request)),
            "post": post,
            "replies": replies,
            "login_url": login_url(request),
        },
    )


STAMP_LABELS = {key: (emoji, label) for key, emoji, label in STAMPS}


@board_open
@require_POST
@login_required
def stamp(request):
    """スタンプを押す・取り消す (つぶやき・返信・回答)。自分の書きこみには押せない"""

    target = request.POST.get("target", "")
    key = request.POST.get("stamp", "")
    target_id = request.POST.get("target_id", "")
    models_by_target = {"post": Post, "reply": PostReply, "answer": Answer}
    if target not in models_by_target or key not in STAMP_LABELS or not target_id.isdigit():
        raise Http404
    obj = get_object_or_404(models_by_target[target], pk=int(target_id), status=Status.PUBLISHED)
    author = obj.author
    fallback = {
        "post": lambda: reverse("chiebukuro:post", args=[obj.pk]),
        "reply": lambda: reverse("chiebukuro:post", args=[obj.post_id]) + f"#r{obj.pk}",
        "answer": lambda: reverse("chiebukuro:question", args=[obj.question_id]) + f"#a{obj.pk}",
    }[target]()

    if author is None or author.pk != request.user.pk:
        deleted, _ = Reaction.objects.filter(target=target, target_id=obj.pk, user=request.user, stamp=key).delete()
        if not deleted:
            try:
                Reaction.objects.create(target=target, target_id=obj.pk, user=request.user, stamp=key, target_author=author)
            except IntegrityError:
                pass
            else:
                emoji, label = STAMP_LABELS[key]
                what = {"post": "つぶやき", "reply": "返信", "answer": "回答"}[target]
                notify(author, Notification.Kind.STAMP, f"あなたの{what}「{short(obj.body, 20)}」に {emoji}{label}", fallback, actor=request.user)
    return redirect(safe_next(request, fallback))


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
            exists = question.answers.filter(author=request.user, body=draft).exists()
            photo_url, error = ("", "") if exists else take_photo(request, "answers")
        if not error:
            if not exists:
                answer = Answer.objects.create(
                    question=question,
                    photo_url=photo_url,
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
    attach_stamps(answers, "answer", request.user)
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
            photo_url = ""
            if question is None:
                photo_url, error = take_photo(request, "questions")
        if not error:
            if question is None:
                question = Question.objects.create(
                    photo_url=photo_url,
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
            photo_url, error = take_photo(request, "items")
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

    mine = active_notices().filter(owner=request.user, is_sample=False).first()
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
            photo_url, error = take_photo(request, "notices")
        if not error:
            notice = Notice.objects.create(
                photo_url=photo_url,
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
    today = timezone.localdate()
    for row in rows:
        day = timezone.localdate(row.created_at)
        row.group = "今日" if day == today else ("昨日" if (today - day).days == 1 else ("この1週間" if (today - day).days < 7 else "それより前"))

    return render(
        request,
        "chiebukuro/notifications.html",
        {**board_context(request, "bell"), "rows": rows, "unread": 0},
    )


@board_open
@login_required
def my_page(request):
    """マイページ: 和食と同じ「メニューの一覧」の形。中身は各ページで"""

    user = request.user
    talks = list(my_talks(user))
    board_profile = BoardProfile.objects.filter(user=user).first()

    return render(
        request,
        "chiebukuro/me.html",
        {
            **board_context(request, "me"),
            "nickname": user_nickname(user),
            "home_region": REGION_LABELS.get(board_profile.region, "") if board_profile else "",
            "intro": board_profile.intro if board_profile else "",
            "counts": {
                "talks": len(talks),
                "unread_talks": sum(1 for talk_request in talks if talk_request.unread_for(user)),
                "posts": Post.objects.filter(author=user, status=Status.PUBLISHED).count(),
                "questions": Question.objects.filter(author=user, status=Status.PUBLISHED).count(),
                "answers": Answer.objects.filter(author=user, status=Status.PUBLISHED).count(),
                "wanted": Interest.objects.filter(user=user, question__status=Status.PUBLISHED).count(),
                "items": Item.objects.filter(owner=user).exclude(status=Status.HIDDEN).count()
                + Notice.objects.filter(owner=user, status=Status.PUBLISHED, is_sample=False).count(),
            },
        },
    )


MY_SECTIONS = {
    "talks": "2人だけのやりとり",
    "posts": "自分のつぶやき",
    "questions": "自分の質問",
    "answers": "自分の回答",
    "wanted": "私も知りたい質問",
    "items": "出しているもの",
}


@board_open
@login_required
def my_list(request, section):

    if section not in MY_SECTIONS:
        raise Http404
    user = request.user
    context = {**board_context(request, "me"), "section": section, "section_title": MY_SECTIONS[section]}

    if section == "talks":
        talks = list(my_talks(user))
        for talk_request in talks:
            talk_request.unread = talk_request.unread_for(user)
            talk_request.other = talk_request.other_name(user)
            talk_request.mine = talk_request.owner_id == user.pk
        context["talks"] = talks
    elif section == "posts":
        context["posts"] = mark_liked(list(
            annotate_posts(Post.objects.filter(author=user, status=Status.PUBLISHED)).select_related("author").order_by("-created_at")[:50]
        ), user)
    elif section in ("questions", "wanted"):
        questions = Question.objects.filter(status=Status.PUBLISHED)
        questions = questions.filter(author=user) if section == "questions" else questions.filter(interests__user=user)
        context["questions"] = list(
            questions.annotate(
                answer_total=Count("answers", filter=Q(answers__status=Status.PUBLISHED), distinct=True),
                interest_total=Count("interests", distinct=True) + F("survey_interest_count"),
            ).order_by("-created_at")[:50]
        )
    elif section == "answers":
        context["answers"] = list(
            Answer.objects.filter(author=user, status=Status.PUBLISHED, question__status=Status.PUBLISHED)
            .select_related("question").order_by("-created_at")[:50]
        )
    else:
        context["items"] = list(Item.objects.filter(owner=user).exclude(status=Status.HIDDEN).order_by("-created_at")[:50])
        context["notices"] = list(Notice.objects.filter(owner=user, status=Status.PUBLISHED, is_sample=False).order_by("-created_at")[:10])

    return render(request, "chiebukuro/my_list.html", context)


@board_open
@login_required
def settings_view(request):
    """設定: 表示 (ダークモード) と、プッシュ通知の頻度・種類"""

    from travel.models import UserProfile

    board_profile, _ = BoardProfile.objects.get_or_create(user=request.user)
    yapp_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    toggles = ["push_answer", "push_reply", "push_stamp", "push_talk"]

    if request.method == "POST":
        theme = request.POST.get("theme", "")
        if theme in dict(UserProfile.THEME_CHOICES):
            yapp_profile.theme_preference = theme
            yapp_profile.save(update_fields=["theme_preference"])
        frequency = request.POST.get("push_frequency", "")
        if frequency in BoardProfile.PushFrequency.values:
            board_profile.push_frequency = frequency
        for field in toggles + ["daily_popup", "color_auto"]:
            setattr(board_profile, field, request.POST.get(field) == "1")
        if request.POST.get("color") in BoardProfile.Color.values:
            board_profile.color = request.POST["color"]
        board_profile.save()
        messages.success(request, "設定を保存しました。")
        return redirect("chiebukuro:settings")

    return render(
        request,
        "chiebukuro/settings.html",
        {
            **board_context(request, "me"),
            "board_profile": board_profile,
            "theme": yapp_profile.theme_preference,
            "themes": UserProfile.THEME_CHOICES,
            "frequencies": BoardProfile.PushFrequency.choices,
            "colors": BoardProfile.Color.choices,
            "toggles": [(field, BoardProfile._meta.get_field(field).verbose_name, getattr(board_profile, field)) for field in toggles],
            "vapid_public_key": getattr(django_settings, "VAPID_PUBLIC_KEY", "") or "",
        },
    )


@login_required
@require_POST
def push_subscribe(request):

    from django.http import JsonResponse

    from news.push_views import parse_subscription

    data = parse_subscription(request)
    if data is None:
        return JsonResponse({"error": "Invalid subscription."}, status=400)
    PushDevice.objects.update_or_create(
        endpoint=data["endpoint"],
        defaults={"user": request.user, "p256dh": data["p256dh"], "auth": data["auth"]},
    )
    return JsonResponse({"success": True})


@login_required
@require_POST
def push_unsubscribe(request):

    import json

    from django.http import JsonResponse

    try:
        endpoint = json.loads(request.body).get("endpoint")
    except (ValueError, UnicodeDecodeError, AttributeError):
        endpoint = None
    if not isinstance(endpoint, str) or not endpoint:
        return JsonResponse({"error": "Invalid endpoint."}, status=400)
    PushDevice.objects.filter(endpoint=endpoint, user=request.user).delete()
    return JsonResponse({"success": True})


@login_required
@require_POST
def push_test(request):

    import json

    from django.http import JsonResponse

    from .push import send

    try:
        endpoint = json.loads(request.body).get("endpoint")
    except (ValueError, UnicodeDecodeError, AttributeError):
        endpoint = None
    devices = list(PushDevice.objects.filter(user=request.user, endpoint=endpoint or ""))
    if not devices:
        return JsonResponse({"error": "Not subscribed."}, status=404)
    if not send(devices, "テスト通知です", "この通知が見えていれば、知恵袋の通知は届きます。", reverse("chiebukuro:settings"), "chiebukuro-test"):
        return JsonResponse({"error": "Send failed."}, status=502)
    return JsonResponse({"success": True})


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
        kind = request.POST.get("avatar_kind", board_profile.avatar_kind)
        if kind in BoardProfile.AvatarKind.values:
            board_profile.avatar_kind = kind
        board_profile.avatar_parts = avatar_art.from_post(request.POST)
        photo_url, photo_error = take_photo(request, "profiles")
        if photo_url:
            board_profile.photo_url = photo_url
        if board_profile.avatar_kind == BoardProfile.AvatarKind.PHOTO and not board_profile.photo_url and not photo_error:
            photo_error = "写真を選んでください。"
        if photo_error:
            error = photo_error
        elif not nickname:
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
            "avatar_groups": avatar_art.choices_for_editor(board_profile.avatar_parts),
            "avatar_kinds": BoardProfile.AvatarKind.choices,
            "error": error,
        },
    )


@login_required
@require_POST
def rules_agree(request):
    profile, _ = BoardProfile.objects.get_or_create(user=request.user)
    profile.rules_agreed_at = timezone.now()
    profile.save(update_fields=["rules_agreed_at"])
    from django.http import JsonResponse

    return JsonResponse({"ok": True})


@board_open
def rules(request):
    return render(request, "chiebukuro/rules.html", board_context(request, "me"))


def avatar_preview(request):
    """編集画面の見本 (選んだ組み合わせのイラスト)"""

    from django.http import HttpResponse

    response = HttpResponse(avatar_art.svg(avatar_art.from_post(request.GET)), content_type="image/svg+xml")
    response["Cache-Control"] = "public, max-age=86400"
    return response


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
        + Reaction.objects.filter(target_author=person).count()
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


@board_open
def install_guide(request):
    """ホーム画面に追加する方法 (SwissNews・和食と同じ案内)"""

    from config.pwa import install_guide_context

    return render(
        request,
        "chiebukuro/install.html",
        {**board_context(request, "install", current_region(request)), **install_guide_context(request, reverse("chiebukuro:home"))},
    )


# =========================================================
# 自分の書きこみの編集・削除
# =========================================================

def _edit_spec(kind):
    """編集できる書きこみと、その欄 (名前, 表示, 種類, 最大文字数, 必須, 選択肢)"""

    body = lambda limit, label="内容": ("body", label, "textarea", limit, True, None)
    region = (lambda name: ("region", "地域", "select", None, False, [("", "指定しない")] + list(BOARD_REGION_CHOICES)))
    specs = {
        "post": {
            "model": Post, "owner": "author", "label": "つぶやき", "photo": "posts", "edited": True,
            "fields": [body(POST_MAX_LENGTH), ("theme", "テーマ", "select", None, False, [("", "なし")] + list(THEMES)), region("region")],
            "back": lambda obj: reverse("chiebukuro:post", args=[obj.pk]),
        },
        "reply": {
            "model": PostReply, "owner": "author", "label": "返信", "photo": "replies", "edited": True,
            "fields": [body(ANSWER_MAX_LENGTH)],
            "back": lambda obj: reverse("chiebukuro:post", args=[obj.post_id]) + f"#r{obj.pk}",
        },
        "question": {
            "model": Question, "owner": "author", "label": "質問", "photo": "questions", "edited": True,
            "fields": [body(QUESTION_MAX_LENGTH, "質問"), ("theme", "テーマ", "select", None, True, list(THEMES)), region("region")],
            "back": lambda obj: reverse("chiebukuro:question", args=[obj.pk]),
        },
        "answer": {
            "model": Answer, "owner": "author", "label": "回答", "photo": "answers", "edited": True,
            "fields": [body(ANSWER_MAX_LENGTH, "回答")],
            "back": lambda obj: reverse("chiebukuro:question", args=[obj.question_id]) + f"#a{obj.pk}",
        },
        "item": {
            "model": Item, "owner": "owner", "label": "ゆずりあい", "photo": "items", "edited": False,
            "fields": [
                ("title", "品物の名前", "text", ITEM_TITLE_MAX_LENGTH, True, None),
                ("body", "説明", "textarea", ITEM_BODY_MAX_LENGTH, False, None),
                ("genre", "ジャンル", "select", None, True, list(Genre.choices)),
                region("region"),
                ("place", "受け渡しの場所", "text", 80, False, None),
            ],
            "back": lambda obj: reverse("chiebukuro:item", args=[obj.pk]),
        },
        "notice": {
            "model": Notice, "owner": "owner", "label": "募集・告知", "photo": "notices", "edited": False,
            "fields": [
                ("title", "タイトル", "text", ITEM_TITLE_MAX_LENGTH, True, None),
                body(NOTICE_BODY_MAX_LENGTH),
                region("region"),
                ("place", "場所", "text", 80, False, None),
                ("event_date", "日にち", "date", None, False, None),
                ("link", "リンク", "url", 500, False, None),
            ],
            "back": lambda obj: reverse("chiebukuro:notice", args=[obj.pk]),
        },
    }
    if kind not in specs:
        raise Http404
    return specs[kind]


@board_open
@login_required
def edit_mine(request, kind, pk):
    """自分の書きこみを直す (写真の差し替え・削除も)"""

    spec = _edit_spec(kind)
    obj = get_object_or_404(spec["model"], pk=pk, status=Status.PUBLISHED, **{spec["owner"]: request.user})
    error = ""
    values = {}
    for name, label, field_type, limit, required, choices in spec["fields"]:
        current = getattr(obj, name)
        values[name] = current.isoformat() if field_type == "date" and current else (current or "")

    if request.method == "POST":
        cleaned = {}
        for name, label, field_type, limit, required, choices in spec["fields"]:
            value = (request.POST.get(name) or "").strip()
            values[name] = value
            if error:
                continue
            if choices is not None and value not in {key for key, _ in choices}:
                error = f"{label}を選んでください。"
            elif required and not value:
                error = f"{label}を入力してください。"
            elif limit and len(value) > limit:
                error = f"{label}は{limit}文字までです。"
            elif field_type == "url" and value and not value.startswith(("https://", "http://")):
                error = "リンクは https:// から始まるURLを入れてください。"
            elif field_type == "date":
                try:
                    value = date.fromisoformat(value) if value else None
                except ValueError:
                    error = "日にちの形が正しくありません。"
            cleaned[name] = value
        photo_url = obj.photo_url
        if not error and request.FILES.get("photo"):
            photo_url, error = take_photo(request, spec["photo"])
        elif request.POST.get("remove_photo") == "yes":
            photo_url = ""
        if not error:
            for name, value in cleaned.items():
                setattr(obj, name, value)
            obj.photo_url = photo_url
            if spec["edited"]:
                obj.edited_at = timezone.now()
            obj.save()
            messages.success(request, f"{spec['label']}を直しました。")
            return redirect(spec["back"](obj))

    fields = [
        {"name": name, "label": label, "type": field_type, "limit": limit, "required": required, "choices": choices, "value": values[name]}
        for name, label, field_type, limit, required, choices in spec["fields"]
    ]
    return render(
        request,
        "chiebukuro/edit.html",
        {
            **board_context(request, {"post": "posts", "reply": "posts", "question": "questions", "answer": "questions", "item": "items", "notice": "notices"}[kind], current_region(request)),
            "obj": obj,
            "kind": kind,
            "kind_label": spec["label"],
            "fields": fields,
            "back_url": spec["back"](obj),
            "error": error,
        },
    )


@board_open
@require_POST
@login_required
def delete_mine(request, kind, pk):
    """質問・返信を消す (つぶやき・回答・ゆずりあい・告知は、それぞれの消すボタンがある)"""

    if kind == "question":
        question = get_object_or_404(Question, pk=pk, author=request.user, status=Status.PUBLISHED)
        if question.answers.filter(status=Status.PUBLISHED).exclude(author=request.user).exists():
            messages.error(request, "ほかの人の回答がついた質問は消せません。内容を直すか、どうしても消したいときは運営に連絡してください。")
            return redirect("chiebukuro:question", pk=pk)
        question.status = Status.HIDDEN
        question.save(update_fields=["status", "updated_at"])
        messages.success(request, "質問を消しました。")
        return redirect("chiebukuro:questions")
    if kind == "reply":
        reply = get_object_or_404(PostReply, pk=pk, author=request.user, status=Status.PUBLISHED)
        reply.status = Status.HIDDEN
        reply.save(update_fields=["status"])
        messages.success(request, "返信を消しました。")
        return redirect(reverse("chiebukuro:post", args=[reply.post_id]) + "#replies")
    raise Http404
