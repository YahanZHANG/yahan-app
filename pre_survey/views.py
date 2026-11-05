"""
事前アンケートの画面

同意 → ニックネーム → テーマ・地域 → 質問に回答 (1問ずつ) → 自分の質問 → 終了
ログインしなくても参加できる。ログインしている人は記録がアカウントにつながる。
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from portal.forms import SignupForm
from portal.views import create_public_user
from travel.models import UserProfile

from .features import COMMENT_MAX_LENGTH, FEATURE_CHOICES, OTHER_MAX_LENGTH
from .models import ANSWER_THEMES, REGION_CHOICES, Answer, FeatureWish, Interest, Participant, Question, Skip, Theme
from .services import (
    TOKEN_COOKIE,
    TOKEN_MAX_AGE,
    browser_token,
    consent_blocks,
    current_consent,
    identity,
    next_question,
    owner_fields,
    random_nickname,
    suggest_username,
)


SESSION_KEY = "pre_survey_participant"

ANSWER_MAX_LENGTH = 1000
QUESTION_MAX_LENGTH = 200
NICKNAME_MAX_LENGTH = 30

# 1回の参加で追加できる質問の数
QUESTIONS_PER_PARTICIPATION = 5

# 地域の初期値 (最初はチューリッヒ周辺の人に送るため)
DEFAULT_REGION = "zurich"

# この数だけ答えたら「ここで終了」を出す
ANSWERS_BEFORE_FINISH = 3


# =========================================================
# Helpers
# =========================================================

def with_token(view):
    """ブラウザの目印を新しく作ったときは cookie に保存する"""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        browser_token(request)
        response = view(request, *args, **kwargs)

        if getattr(request, "_pre_survey_new_token", False):
            response.set_cookie(
                TOKEN_COOKIE,
                str(request._pre_survey_token),
                max_age=TOKEN_MAX_AGE,
                httponly=True,
                samesite="Lax",
                secure=request.is_secure(),
            )

        return response

    return wrapper


def current_participant(request):
    """いまの参加。なければ None。途中でログインしたら、この参加の記録をアカウントにつなげる。"""

    participant_id = request.session.get(SESSION_KEY)

    if not participant_id:
        return None

    participant = Participant.objects.filter(
        pk=participant_id,
        browser_token=browser_token(request),
    ).first()

    if participant is None:
        return None

    user = request.user

    if user.is_authenticated and participant.user_id is None:
        with transaction.atomic():
            participant.user = user
            participant.save(update_fields=["user"])
            for model in (Answer, Question, Interest, Skip, FeatureWish):
                model.objects.filter(participant=participant, user=None).update(user=user)

    elif user.is_authenticated and participant.user_id != user.pk:
        # 同じブラウザで別の人がログインした: その人の参加ではない
        return None

    return participant


def step_redirect(participant):
    """まだ済んでいない段階へ"""

    if participant is None:
        return redirect("pre_survey:start")
    if not participant.nickname_mode:
        return redirect("pre_survey:nickname")
    if not participant.themes:
        return redirect("pre_survey:themes")
    return None


def profile_nickname(user):
    if not user.is_authenticated:
        return ""
    profile = UserProfile.objects.filter(user=user).only("nickname").first()
    return profile.nickname if profile else ""


def login_url(request, path=None):
    return f"{reverse('login')}?next={path or request.path}"


def theme_options(selected):
    return [
        {"value": value, "label": label, "checked": value in selected}
        for value, label in ANSWER_THEMES
    ]


# =========================================================
# 1. 趣旨説明と同意
# =========================================================

@with_token
def start(request):

    version, text = current_consent()

    if request.method == "POST":

        if request.POST.get("agree") != "yes":
            messages.error(request, "内容をご確認のうえ、「同意して始める」を押してください。")
            return redirect("pre_survey:start")

        participant = Participant.objects.create(
            browser_token=browser_token(request),
            user=request.user if request.user.is_authenticated else None,
            consent_version=version,
            consented_at=timezone.now(),
        )
        request.session[SESSION_KEY] = participant.pk
        return redirect("pre_survey:nickname")

    return render(
        request,
        "pre_survey/start.html",
        {
            "consent_blocks": consent_blocks(text),
            "consent_version": version,
            "login_url": login_url(request),
            "nickname": profile_nickname(request.user),
            "step": 1,
        },
    )


# =========================================================
# 2. ニックネーム
# =========================================================

@with_token
def nickname(request):

    participant = current_participant(request)

    if participant is None:
        return redirect("pre_survey:start")

    error = ""
    auto_name = request.POST.get("auto_name") or random_nickname()
    custom_name = participant.nickname if participant.nickname_mode == "custom" else profile_nickname(request.user)
    mode = participant.nickname_mode or ("custom" if custom_name else "")

    if request.method == "POST":

        mode = request.POST.get("mode", "")
        custom_name = (request.POST.get("custom_name") or "").strip()

        if request.POST.get("reroll"):
            # 「ほかの名前にする」: おまかせの名前だけ変えて、もう一度表示
            auto_name = random_nickname(avoid=auto_name)
            mode = "auto"

        elif mode == "custom" and not custom_name:
            error = "ニックネームを入力してください。"

        elif mode == "custom" and len(custom_name) > NICKNAME_MAX_LENGTH:
            error = f"ニックネームは{NICKNAME_MAX_LENGTH}文字までです。"

        elif mode in Participant.NicknameMode.values:
            participant.nickname_mode = mode
            participant.nickname = {
                "custom": custom_name,
                "auto": auto_name[:NICKNAME_MAX_LENGTH],
                "anonymous": "",
            }[mode]
            participant.save(update_fields=["nickname_mode", "nickname"])
            return redirect("pre_survey:themes")

        else:
            error = "ニックネームの決め方を選んでください。"

    return render(
        request,
        "pre_survey/nickname.html",
        {
            "participant": participant,
            "mode": mode,
            "custom_name": custom_name,
            "auto_name": auto_name,
            "error": error,
            "max_length": NICKNAME_MAX_LENGTH,
            "step": 2,
        },
    )


# =========================================================
# 3. テーマと地域
# =========================================================

@with_token
def themes(request):

    participant = current_participant(request)

    if participant is None or not participant.nickname_mode:
        return step_redirect(participant)

    error = ""
    # 「さらに他の質問に答える」では、前回のテーマ・地域が引き継がれている (again)
    selected = participant.themes
    # 地域は、はじめて選ぶときはチューリッヒを選んだ状態にしておく
    region = participant.region if participant.themes else (participant.region or DEFAULT_REGION)

    if request.method == "POST":

        selected = [value for value in request.POST.getlist("themes") if value in dict(ANSWER_THEMES)]
        region = request.POST.get("region", "")

        if region not in dict(REGION_CHOICES):
            region = ""

        if not selected:
            error = "テーマを1つ以上選んでください。"
        else:
            participant.themes = selected
            participant.region = region
            participant.save(update_fields=["themes", "region"])

            following = "ask" if request.POST.get("next") == "ask" else "question"

            if needs_wish(request, participant):
                return redirect(f"{reverse('pre_survey:wish')}?next={following}")
            return redirect(f"pre_survey:{following}")

    return render(
        request,
        "pre_survey/themes.html",
        {
            "participant": participant,
            "theme_options": theme_options(selected),
            "regions": REGION_CHOICES,
            "region": region,
            "error": error,
            "step": 3,
        },
    )


# =========================================================
# 4-0. 「0問目」: 掲示板に求める機能 (任意)
# =========================================================

def needs_wish(request, participant):
    """
    「0問目」をまだ出していないか。
    答えた・「前に回答しました」を押した人には、もう出さない。スキップした人には、次の参加でもう一度だけ出す。
    """

    if participant.feature_wishes.exists():
        return False

    return not FeatureWish.objects.filter(
        identity(request),
        response__in=[FeatureWish.Response.ANSWERED, FeatureWish.Response.ALREADY],
    ).exists()


@with_token
def wish(request):

    participant = current_participant(request)
    redirect_to = step_redirect(participant)

    if redirect_to:
        return redirect_to

    following = "ask" if (request.POST.get("next") or request.GET.get("next")) == "ask" else "question"
    keys = dict(FEATURE_CHOICES)
    selected = []
    other_text = ""
    comment = ""
    error = ""

    if request.method == "POST":

        action = request.POST.get("action")
        selected = [key for key in request.POST.getlist("features") if key in keys]
        other_text = (request.POST.get("other_text") or "").strip()[:OTHER_MAX_LENGTH]
        comment = (request.POST.get("comment") or "").strip()

        if action in ("skip", "already"):
            FeatureWish.objects.create(
                response=FeatureWish.Response.SKIPPED if action == "skip" else FeatureWish.Response.ALREADY,
                **owner_fields(request, participant),
            )
            return redirect(f"pre_survey:{following}")

        if len(comment) > COMMENT_MAX_LENGTH:
            error = f"ご意見は{COMMENT_MAX_LENGTH}文字までです。"
        elif not selected and not comment:
            error = "あてはまるものを選ぶか、「スキップ」を押してください。"
        else:
            if not participant.feature_wishes.exists():
                FeatureWish.objects.create(
                    response=FeatureWish.Response.ANSWERED,
                    features=selected,
                    other_text=other_text if "other" in selected else "",
                    comment=comment,
                    **owner_fields(request, participant),
                )
            messages.success(request, "ご意見ありがとうございます！ 続いて、質問にお答えください。" if following == "question" else "ご意見ありがとうございます！")
            return redirect(f"pre_survey:{following}")

    return render(
        request,
        "pre_survey/wish.html",
        {
            "participant": participant,
            "choices": [{"key": key, "label": label, "checked": key in selected} for key, label in FEATURE_CHOICES],
            "other_text": other_text,
            "comment": comment,
            "error": error,
            "next": following,
            "other_max_length": OTHER_MAX_LENGTH,
            "comment_max_length": COMMENT_MAX_LENGTH,
            "step": 4,
        },
    )


# =========================================================
# 4. 質問に回答 (1問ずつ)
# =========================================================

@with_token
def question(request):

    participant = current_participant(request)
    redirect_to = step_redirect(participant)

    if redirect_to:
        return redirect_to

    if needs_wish(request, participant):
        return redirect(f"{reverse('pre_survey:wish')}?next=question")

    answered_count = participant.answers.count()

    # 「元に戻す」で戻ってきた質問、または回答の入力エラーで出し直す質問
    shown = None
    shown_id = request.GET.get("show", "")

    if shown_id.isdigit():
        shown = (
            Question.objects
            .filter(pk=shown_id, status=Question.Status.PUBLISHED)
            .exclude(pk__in=Answer.objects.filter(identity(request)).values("question_id"))
            .first()
        )

    current = shown or next_question(request, participant)

    skipped = None
    skipped_id = request.GET.get("skipped", "")

    if skipped_id.isdigit():
        skipped = Skip.objects.filter(participant=participant, question_id=skipped_id).first()

    return render(
        request,
        "pre_survey/question.html",
        {
            "participant": participant,
            "question": current,
            "answered_count": answered_count,
            "can_finish": answered_count >= ANSWERS_BEFORE_FINISH,
            "answers_before_finish": ANSWERS_BEFORE_FINISH,
            "skipped": skipped,
            "interested": request.GET.get("interested") == "1",
            "answered": request.GET.get("answered") == "1",
            "draft": request.session.pop("pre_survey_draft", ""),
            "max_length": ANSWER_MAX_LENGTH,
            "login_url": login_url(request),
            "step": 4,
        },
    )


@require_POST
@with_token
def question_action(request, pk):
    """回答する・スキップ・私も知りたい"""

    participant = current_participant(request)
    redirect_to = step_redirect(participant)

    if redirect_to:
        return redirect_to

    target = get_object_or_404(Question, pk=pk, status=Question.Status.PUBLISHED)
    action = request.POST.get("action")
    url = reverse("pre_survey:question")

    if action == "answer":

        body = (request.POST.get("body") or "").strip()

        if not body or len(body) > ANSWER_MAX_LENGTH:
            if body:
                messages.error(request, f"回答は{ANSWER_MAX_LENGTH}文字までです。")
                request.session["pre_survey_draft"] = body
            else:
                messages.error(request, "回答を入力してください。答えにくい場合は「スキップ」を押してください。")
            return redirect(f"{url}?show={target.pk}")

        # 二度押し・戻って再送信: 同じ人が同じ質問にもう答えていたら、追加しない
        already = Answer.objects.filter(identity(request), question=target).exists()

        if not already:
            Answer.objects.create(
                question=target,
                body=body,
                nickname=participant.nickname,
                publish_consent=True,
                **owner_fields(request, participant),
            )

        return redirect(f"{url}?answered=1")

    if action == "skip":
        Skip.objects.get_or_create(
            question=target,
            participant=participant,
            defaults=owner_fields(request, participant),
        )
        return redirect(f"{url}?skipped={target.pk}")

    if action == "interest":
        existing = Interest.objects.filter(identity(request), question=target).first()

        if existing:
            # 前の参加でも「知りたい」にしていた: この参加でも出さないように付け替える
            existing.participant = participant
            existing.save(update_fields=["participant"])
        else:
            Interest.objects.create(question=target, **owner_fields(request, participant))

        return redirect(f"{url}?interested=1")

    return redirect(url)


@require_POST
@with_token
def undo_skip(request, pk):

    participant = current_participant(request)

    if participant is None:
        return redirect("pre_survey:start")

    Skip.objects.filter(participant=participant, question_id=pk).delete()
    return redirect(f"{reverse('pre_survey:question')}?show={pk}")


# =========================================================
# 5. 自分の質問を追加
# =========================================================

@with_token
def ask(request):

    participant = current_participant(request)
    redirect_to = step_redirect(participant)

    if redirect_to:
        return redirect_to

    asked = list(participant.questions.order_by("created_at"))
    # 回答画面の「ここで終了」から来た: 最後に質問を聞いてから終わる
    last = (request.POST.get("last") or request.GET.get("last")) == "1"
    error = ""
    body = ""
    theme = participant.themes[0] if participant.themes else Theme.LIFE

    if request.method == "POST":

        body = (request.POST.get("body") or "").strip()
        theme = request.POST.get("theme", "")

        if len(asked) >= QUESTIONS_PER_PARTICIPATION:
            error = f"1回の参加で追加できる質問は{QUESTIONS_PER_PARTICIPATION}問までです。終了画面の「さらに他の質問に答える」から、また追加できます。"
        elif theme not in Theme.values:
            error = "テーマを選んでください。"
        elif not body:
            error = "質問を入力してください。"
        elif len(body) > QUESTION_MAX_LENGTH:
            error = f"質問は{QUESTION_MAX_LENGTH}文字までです。"
        else:
            # 二度押し: 同じ参加で同じ質問がもうあれば追加しない
            if not participant.questions.filter(body=body).exists():
                Question.objects.create(
                    body=body,
                    theme=theme,
                    region=participant.region,
                    source=Question.Source.MEMBER,
                    nickname=participant.nickname,
                    **owner_fields(request, participant),
                )
            messages.success(request, "質問を追加しました。ありがとうございます。")
            url = reverse("pre_survey:ask")
            return redirect(f"{url}?last=1" if last else url)

    return render(
        request,
        "pre_survey/ask.html",
        {
            "participant": participant,
            "asked": asked,
            "remaining": max(QUESTIONS_PER_PARTICIPATION - len(asked), 0),
            "limit": QUESTIONS_PER_PARTICIPATION,
            "theme_choices": Theme.choices,
            "theme": theme,
            "body": body,
            "error": error,
            "max_length": QUESTION_MAX_LENGTH,
            "answered_count": participant.answers.count(),
            "last": last,
            "step": 5,
        },
    )


# =========================================================
# 6. 終了
# =========================================================

def signup_offer(request, participant):
    """
    ログインしていない人には「このままYappに登録」を出す。
    ニックネームがあれば (自分で決めた・おまかせ)、それをユーザーIDの初期値にする。
    """

    return not request.user.is_authenticated


@with_token
def done(request):

    participant = current_participant(request)

    if participant is None:
        return redirect("pre_survey:start")

    if participant.finished_at is None:
        participant.finished_at = timezone.now()
        participant.save(update_fields=["finished_at"])

    context = {
        "participant": participant,
        "answered_count": participant.answers.count(),
        "asked_count": participant.questions.count(),
        "can_ask": participant.questions.count() < QUESTIONS_PER_PARTICIPATION,
        "interest_count": participant.interests.count(),
        "step": 6,
    }

    if signup_offer(request, participant):
        username, taken = suggest_username(participant.nickname)
        context.update({
            "signup_form": SignupForm(initial={"username": username}),
            "nickname_taken": taken,
            "login_url": login_url(request, reverse("pre_survey:done")),
        })

    return render(request, "pre_survey/done.html", context)


@require_POST
@with_token
def done_signup(request):

    participant = current_participant(request)

    if participant is None:
        return redirect("pre_survey:start")

    if not signup_offer(request, participant):
        return redirect("pre_survey:done")

    form = SignupForm({
        "username": request.POST.get("username", ""),
        "email": "",
        "password1": request.POST.get("password1", ""),
        "password2": request.POST.get("password2", ""),
    })

    if not form.is_valid():
        username, taken = suggest_username(request.POST.get("username", "") or participant.nickname)
        return render(
            request,
            "pre_survey/done.html",
            {
                "participant": participant,
                "answered_count": participant.answers.count(),
                "asked_count": participant.questions.count(),
                "can_ask": participant.questions.count() < QUESTIONS_PER_PARTICIPATION,
                "interest_count": participant.interests.count(),
                "signup_form": form,
                "suggested_username": username if "username" in form.errors else "",
                "login_url": login_url(request, reverse("pre_survey:done")),
                "step": 6,
            },
        )

    with transaction.atomic():
        user = create_public_user(form, nickname=participant.nickname)

        # このブラウザでの、これまでの事前アンケートの記録をアカウントにつなげる
        token = browser_token(request)
        Participant.objects.filter(browser_token=token, user=None).update(user=user)
        for model in (Answer, Question, Interest, Skip, FeatureWish):
            model.objects.filter(browser_token=token, user=None).update(user=user)

    login(request, user, backend="portal.backends.EmailOrUsernameBackend")
    messages.success(request, "Yappに登録しました。ようこそ！")
    return redirect("pre_survey:done")


@require_POST
@with_token
def again(request):
    """さらに他の質問に答える: 同意・ニックネーム・テーマ・地域は前回のまま、すぐ次の質問へ"""

    previous = current_participant(request)

    if previous is None:
        return redirect("pre_survey:start")

    version, _ = current_consent()

    if previous.consent_version != version:
        # 同意文が変わっていたら、もう一度読んでもらう
        request.session.pop(SESSION_KEY, None)
        return redirect("pre_survey:start")

    participant = Participant.objects.create(
        browser_token=browser_token(request),
        user=request.user if request.user.is_authenticated else None,
        nickname=previous.nickname,
        nickname_mode=previous.nickname_mode,
        themes=previous.themes,
        region=previous.region,
        consent_version=previous.consent_version,
        consented_at=previous.consented_at,
    )
    request.session[SESSION_KEY] = participant.pk
    return redirect("pre_survey:question")
