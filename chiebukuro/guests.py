"""
登録なしの書きこみ (名無しさん)。

ID・パスワードを決めなくても、質問・回答を書けるようにする。送信したときに、裏で
「ゲスト」のアカウントを作ってログインする (サイレントログイン)。同じ端末なら、そのあとも
同じ人として続けられる (お知らせ・自分の質問)。あとから ID とパスワードを決めれば、
ほかの端末からも使えるふつうのアカウントになる。

事前アンケートでゆずりあいの希望を書いた人 (アカウントなし) にも、同じゲストのアカウントを
作って品物を出す。その人がアンケートに答えた端末で掲示板を開くと、自動でそのアカウントになる。
"""

import uuid

from django.contrib.auth import get_user_model, login
from django.core.cache import cache
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone

GUEST_NAME = "名無しさん"
# settings.AUTHENTICATION_BACKENDS にあるもの (ここにないと、次のページでログインが外れる)
LOGIN_BACKEND = "portal.backends.EmailOrUsernameBackend"
# 1つの IP から1日に作れるゲストの数 (荒らし対策)
GUEST_PER_IP_PER_DAY = 6


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")) or "?"


def make_guest(nickname="", email="", token=None, agreed=True):
    """ゲストのアカウントを作る (ログインはしない)"""

    from django.contrib.auth.models import Group

    from travel.models import UserProfile

    from .models import BoardProfile

    User = get_user_model()
    user = User(username=f"guest_{uuid.uuid4().hex[:12]}", is_active=True, email=email)
    user.set_unusable_password()
    user.save()
    group, _ = Group.objects.get_or_create(name="public_users")
    user.groups.add(group)
    nickname = (nickname or "").strip()[:30] or GUEST_NAME
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.nickname = nickname
    for field in ("password_setup_completed", "nickname_setup_completed"):
        if hasattr(profile, field):
            setattr(profile, field, True)
    profile.save()
    BoardProfile.objects.update_or_create(
        user=user,
        defaults={
            "is_guest": True,
            "guest_token": token,
            "email_answer": bool(email),
            "rules_agreed_at": timezone.now() if agreed else None,
        },
    )
    return user


def guest_fields(request):
    """フォームの「登録なしで書く」の欄: (nickname, email, error)"""

    nickname = (request.POST.get("guest_nickname") or "").strip()[:30]
    email = (request.POST.get("guest_email") or "").strip()[:200]
    if email:
        try:
            validate_email(email)
        except ValidationError:
            return nickname, email, "メールアドレスの形が正しくありません（空でも送れます）。"
    return nickname, email, ""


def sign_in_guest(request, nickname="", email=""):
    """
    ログインしていない人が書きこむとき、ゲストのアカウントを作ってログインする。
    荒らし対策: 見えない欄 (website) に何か入っていたら、または同じ IP から作りすぎたら None。
    """

    if request.user.is_authenticated:
        return request.user
    if request.POST.get("website"):
        return None
    key = f"chie-guest-{client_ip(request)}-{timezone.localdate():%Y%m%d}"
    count = cache.get(key, 0)
    if count >= GUEST_PER_IP_PER_DAY:
        return None
    cache.set(key, count + 1, 60 * 60 * 26)
    user = make_guest(nickname, email, token=survey_token(request))
    login(request, user, backend=LOGIN_BACKEND)
    return user


def survey_token(request):
    from pre_survey.services import TOKEN_COOKIE

    try:
        return uuid.UUID(request.COOKIES.get(TOKEN_COOKIE, ""))
    except ValueError:
        return None


def silent_login(request):
    """事前アンケートに答えた端末で開いたら、その人のゲストのアカウントにする"""

    if request.user.is_authenticated:
        return
    token = survey_token(request)
    if token is None:
        return
    from .models import BoardProfile

    profile = BoardProfile.objects.filter(guest_token=token, is_guest=True).select_related("user").first()
    if profile and profile.user.is_active:
        login(request, profile.user, backend=LOGIN_BACKEND)


def is_guest(user):
    if not getattr(user, "is_authenticated", False):
        return False
    from .models import BoardProfile

    return BoardProfile.objects.filter(user=user, is_guest=True).exists()
