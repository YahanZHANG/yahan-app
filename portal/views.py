from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
)
from django.contrib.auth import views as auth_views
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator

from django.core.mail import send_mail
from django.core import signing

from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.utils.encoding import (
    force_bytes,
    force_str,
)
from django.utils.http import (
    urlsafe_base64_decode,
    urlsafe_base64_encode,
    url_has_allowed_host_and_scheme
)

from board.models import BoardPost
from board.permissions import can_post_board
from chat.models import (
    ChatConnection,
    ChatMessage,
)
from feeding.models import BabyMembership
from travel.models import UserProfile
from usage_analytics.permissions import can_view_analytics

from .forms import (
    AppSelectionForm,
    NicknameForm,
    SignupForm,
    ResendVerificationForm,
)
from .models import (
    AppAccessRequest,
    AppIdea,
    PortalAnnouncement,
    PortalSettings,
    PortalAppPreference,
)

from django.db.models import Q

from chat.models import (
    ChatMessage,
    ChatConnection,
)

from urllib.parse import urlencode


# =========================================================
# Portal app definitions
# =========================================================

APP_CONFIG = {
    "news": {
        "name": "スイスニュース",
        "label": "SWISS NEWS",
        "icon": "📰",
        "url_name": "news:home",
        "card_class": "portal-news-card",
        "icon_class": "portal-news-icon",
        "description": (
            "スイスの最新ニュースを日本語でチェック。"
            "現地の情報をいち早くキャッチ。"
        ),
    },
    "feeding": {
        "name": "離乳食記録",
        "label": "BABY FOOD",
        "icon": "🥣",
        "url_name": "feeding:today",
        "card_class": "portal-feeding-card",
        "icon_class": "portal-feeding-icon",
        "description": (
                "赤ちゃんの離乳食を簡単に管理・記録。"
                "アレルギーや毎日の歯磨きの記録も。"
            ),
    },
    "vaccination": {
        "name": "予防接種",
        "label": "VACCINATION",
        "icon": "💉",
        "url_name": "vaccination:home",
        "card_class": "portal-vaccination-card",
        "icon_class": "portal-vaccination-icon",
        "description": (
            "赤ちゃんの予防接種を簡単に管理・記録。"
            "多言語対応で旅行中も安心。"
        ),
    },
    "recipes": {
        "name": "レシピ検索",
        "label": "RECIPE FINDER",
        "icon": "🍳",
        "url_name": "recipes:home",
        "card_class": "portal-recipes-card",
        "icon_class": "portal-recipes-icon",
        "description": (
            "ホットクックやシェフドラムを使ったレシピを検索。"
            "毎日の献立づくりをサポート。"
        ),
    },
    "games": {
        "name": "ゲーム",
        "label": "MINI GAMES",
        "icon": "🎮",
        "url_name": "games:game_list",
        "card_class": "portal-games-card",
        "icon_class": "portal-games-icon",
        "description": (
            "ちょっとした空き時間に楽しめるミニゲーム。"
        ),
    },
    "colorcheck": {
        "name": "色判定",
        "label": "COLOR CHECKER",
        "icon": "🎨",
        "url_name": "colorcheck:index",
        "card_class": "portal-colorcheck-card",
        "icon_class": "portal-colorcheck-icon",
        "description": (
            "色の認識に悩む方のために。"
            "気になる色の情報を3段階の細かさで簡単に確認。"
        ),
    },    
    "events": {

        "name":
            "イベント・日程調整",

        "label":
            "EVENT SCHEDULER",

        "icon":
            "📅",

        "url_name":
            "event_scheduler:event_list",

        "card_class":
            "portal-events-card",

        "icon_class":
            "portal-events-icon",

        "description": (
            "イベントを作成して、みんなの予定を簡単に調整。"
            "候補日や時間、イベントの長さもまとめて決められる。"
        ),
    },

    "chat": {

        "name":
            "チャット",

        "label":
            "CHAT",

        "icon":
            "💬",

        "url_name":
            "chat:list",

        "card_class":
            "portal-chat-app-card",

        "icon_class":
            "portal-chat-app-icon",

        "description": (
            "Appのユーザー同士でメッセージ。"
            "友だちと気軽にやりとりできる。"
        ),

    },
}


# =========================================================
# Safe redirect after signup
# =========================================================

SIGNUP_RETURN_SALT = "yapp-signup-return"


def get_safe_next(request, value):
    """
    Yapp内の安全な戻り先URLのみ許可。
    """

    if not value:
        return ""

    if not value.startswith("/") or value.startswith("//"):
        return ""

    if not url_has_allowed_host_and_scheme(
        url=value,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return ""

    return value


def make_signup_return_token(request, next_url):
    """
    メール認証リンクに載せる署名付き戻り先。
    """

    safe_next = get_safe_next(request, next_url)

    if not safe_next:
        return ""

    return signing.dumps(
        safe_next,
        salt=SIGNUP_RETURN_SALT,
    )


def read_signup_return_token(request, token):
    """
    48時間以内の署名付き戻り先を復元。
    """

    if not token:
        return ""

    try:
        next_url = signing.loads(
            token,
            salt=SIGNUP_RETURN_SALT,
            max_age=60 * 60 * 48,
        )

    except signing.BadSignature:
        return ""

    return get_safe_next(request, next_url)


def redirect_after_signup(request):
    """
    ニックネーム設定後、元のサービスへ戻る。
    """

    next_url = request.session.pop(
        "yapp_post_signup_next",
        "",
    )

    safe_next = get_safe_next(request, next_url)

    if safe_next:
        return redirect(safe_next)

    return redirect("portal:home")


# =========================================================
# Public signup users
# =========================================================

PUBLIC_USER_GROUP = "public_users"


PUBLIC_APP_KEYS = [
    "news",
    "recipes",
    "events",
    "colorcheck",
    "games",
]

# =========================================================
# Helpers
# =========================================================

def ensure_app_preferences(user):
    """
    ユーザーが利用できるアプリについて、
    Portal設定が存在しなければ作成する。
    """

    available_choices = (
        get_app_choices_for_user(
            user
        )
    )

    for index, (app_key, label) in enumerate(
        available_choices
    ):

        PortalAppPreference.objects.get_or_create(
            user=user,
            app_key=app_key,
            defaults={
                "is_visible": True,
                "display_order": index,
            },
        )


def redirect_to_setup_if_needed(profile):
    """
    初回設定が未完了の場合、
    必要な設定画面へ誘導する。

    アプリ選択は不要。
    """

    if not profile.password_setup_completed:
        return "portal:password_setup"

    if not profile.nickname_setup_completed:
        return "portal:nickname_setup"

    return None


def is_public_user(user):

    return (
        user.is_authenticated
        and user.groups.filter(
            name=PUBLIC_USER_GROUP
        ).exists()
    )


def get_approved_app_keys(user):

    if not user.is_authenticated:
        return set()

    return set(
        AppAccessRequest.objects.filter(
            user=user,
            status=AppAccessRequest.Status.APPROVED,
        ).values_list(
            "app_key",
            flat=True,
        )
    )


def get_app_choices_for_user(user):

    # 既存のプライベートユーザーは従来どおり全部利用可能
    if not is_public_user(user):
        return PortalAppPreference.AppKey.choices


    # 一般公開アプリ
    allowed_keys = set(
        PUBLIC_APP_KEYS
    )


    # 管理者が個別に承認したアプリを追加
    allowed_keys.update(
        get_approved_app_keys(
            user
        )
    )


    return [
        (value, label)
        for value, label
        in PortalAppPreference.AppKey.choices
        if value in allowed_keys
    ]

# =========================================================
# Public signup
# =========================================================

SIGNUP_RESUBMIT_WINDOW = timedelta(minutes=30)


def start_signed_up_session(request, user, next_url):
    """
    作成したばかりのアカウントでログインし、
    ニックネーム設定へ進める。
    """

    login(
        request,
        user,
        backend=(
            "portal.backends."
            "EmailOrUsernameBackend"
        ),
    )

    if next_url:
        request.session[
            "yapp_post_signup_next"
        ] = next_url
    else:
        request.session.pop(
            "yapp_post_signup_next",
            None,
        )

    return redirect("portal:nickname_setup")


def find_resubmitted_signup(request):
    """
    「作成」を2回押した・戻って再送信した場合、
    直前に作られた同じアカウントを返す。
    パスワードが一致したときだけ。
    """

    username = (
        request.POST.get("username")
        or ""
    ).strip()

    password = request.POST.get(
        "password1"
    ) or ""

    if not username or not password:
        return None

    exists = (
        get_user_model()
        .objects
        .filter(
            username__iexact=username,
            date_joined__gte=(
                timezone.now()
                - SIGNUP_RESUBMIT_WINDOW
            ),
        )
        .exists()
    )

    if not exists:
        return None

    # axes の失敗回数にも数えられるよう、通常の認証を通す
    return authenticate(
        request,
        username=username,
        password=password,
    )


def signup(request):

    next_url = get_safe_next(
        request,
        request.POST.get("next")
        or request.GET.get("next", ""),
    )

    if request.user.is_authenticated:

        return redirect(
            "portal:home"
        )

    if request.method == "POST":

        resubmitted_user = find_resubmitted_signup(
            request
        )

        if resubmitted_user is not None:

            return start_signed_up_session(
                request,
                resubmitted_user,
                next_url,
            )

        form = SignupForm(
            request.POST
        )

        if form.is_valid():

            # =================================================
            # Create user (すぐに使える状態で作成)
            # =================================================

            user = form.save(
                commit=False
            )

            user.email = (
                form.cleaned_data[
                    "email"
                ]
            )

            user.is_active = True

            user.save()


            # =================================================
            # Public user group
            # =================================================

            public_group, _ = (
                Group.objects.get_or_create(
                    name=PUBLIC_USER_GROUP
                )
            )

            user.groups.add(
                public_group
            )


            # =================================================
            # Profile
            # =================================================

            profile, _ = (
                UserProfile.objects.get_or_create(
                    user=user
                )
            )

            # Signup時にパスワードは設定済み
            profile.password_setup_completed = True

            profile.nickname_setup_completed = False
            profile.app_setup_completed = False

            profile.save()


            messages.success(
                request,
                "アカウントを作成しました。Yappへようこそ！",
            )

            return start_signed_up_session(
                request,
                user,
                next_url,
            )

    else:

        form = SignupForm()

    return render(
        request,
        "registration/signup.html",
        {
            "form": form,
            "next_url": next_url,
        },
    )

def resend_verification(request):

    if request.user.is_authenticated:

        return redirect(
            "portal:home"
        )

    if request.method == "POST":

        form = ResendVerificationForm(
            request.POST
        )

        if form.is_valid():

            email = (
                form.cleaned_data[
                    "email"
                ]
            )

            user = (
                get_user_model()
                .objects
                .filter(
                    email__iexact=email,
                    is_active=False,
                )
                .first()
            )

            if user is not None:

                uid = urlsafe_base64_encode(
                    force_bytes(
                        user.pk
                    )
                )

                token = (
                    default_token_generator
                    .make_token(
                        user
                    )
                )

                verification_url = (
                    request.build_absolute_uri(
                        reverse(
                            "portal:verify_email",
                            kwargs={
                                "uidb64": uid,
                                "token": token,
                            },
                        )
                    )
                )

                subject = (
                    "【Yapp】"
                    "メールアドレスを確認してください"
                )

                message = (
                    "Yappへようこそ。\n\n"
                    "以下のリンクを開いて、"
                    "メールアドレスを確認してください。\n\n"
                    f"{verification_url}\n\n"
                    "このメールに心当たりがない場合は、"
                    "そのまま破棄してください。\n\n"
                    "Yapp"
                )

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=(
                        settings.DEFAULT_FROM_EMAIL
                    ),
                    recipient_list=[
                        user.email
                    ],
                    fail_silently=True,
                )

            # 存在するメールかどうかは明かさない
            return render(
                request,
                (
                    "registration/"
                    "verification_email_resent.html"
                ),
                {
                    "email": email,
                },
            )

    else:

        form = ResendVerificationForm()

    return render(
        request,
        "registration/resend_verification.html",
        {
            "form": form,
        },
    )

def verify_email(
    request,
    uidb64,
    token,
):

    # =====================================================
    # Find user
    # =====================================================

    try:

        user_id = force_str(
            urlsafe_base64_decode(
                uidb64
            )
        )

        user = (
            get_user_model()
            .objects
            .get(
                pk=user_id
            )
        )

    except (
        TypeError,
        ValueError,
        OverflowError,
        get_user_model().DoesNotExist,
    ):

        user = None


    # =====================================================
    # Invalid link
    # =====================================================

    if (
        user is None
        or not default_token_generator.check_token(
            user,
            token,
        )
    ):

        return render(
            request,
            "registration/email_verification_invalid.html",
        )


    # =====================================================
    # Already verified
    # =====================================================

    if user.is_active:

        messages.info(
            request,
            (
                "このメールアドレスは"
                "すでに確認済みです。"
            ),
        )

        return redirect(
            "login"
        )


    # =====================================================
    # Activate
    # =====================================================

    user.is_active = True

    user.save(
        update_fields=[
            "is_active",
        ]
    )


    # =====================================================
    # Login
    # =====================================================

    login(
        request,
        user,
        backend=(
            "portal.backends."
            "EmailOrUsernameBackend"
        ),
    )


    messages.success(
        request,
        (
            "メールアドレスを確認しました。"
            "Yappへようこそ！"
        ),
    )


        
    return_token = request.GET.get(
        "return_token",
        "",
    )

    next_url = read_signup_return_token(
        request,
        return_token,
    )

    if next_url:
        request.session[
            "yapp_post_signup_next"
        ] = next_url
    else:
        request.session.pop(
            "yapp_post_signup_next",
            None,
        )

    return redirect("portal:nickname_setup")


# =========================================================
# Normal password change
# =========================================================

class PortalPasswordChangeView(
    auth_views.PasswordChangeView
):

    template_name = (
        "registration/password_change_form.html"
    )

    # -----------------------------------------------------
    # Safe return URL
    # -----------------------------------------------------

    def get_return_url(self):

        next_url = (
            self.request.POST.get("next")
            or self.request.GET.get("next", "")
        )

        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return next_url

        return reverse("portal:home")

    # -----------------------------------------------------
    # Template context
    # -----------------------------------------------------

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context["return_url"] = self.get_return_url()

        return context

    # -----------------------------------------------------
    # After password change
    # -----------------------------------------------------

    def get_success_url(self):

        return (
            reverse("password_change_done")
            + "?"
            + urlencode({
                "next": self.get_return_url(),
            })
        )

# =========================================================
# Initial password setup
# =========================================================

class InitialPasswordSetupView(
    auth_views.PasswordChangeView
):
    template_name = (
        "registration/password_change_form.html"
    )

    form_class = SetPasswordForm


    def dispatch(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return redirect("login")

        profile, _ = UserProfile.objects.get_or_create(
            user=request.user
        )

        if profile.password_setup_completed:

            if not profile.nickname_setup_completed:
                return redirect(
                    "portal:nickname_setup"
                )

            return redirect("portal:home")

        return super().dispatch(
            request,
            *args,
            **kwargs,
        )


    def form_valid(self, form):

        profile, _ = (
            UserProfile.objects.get_or_create(
                user=self.request.user
            )
        )

        profile.password_setup_completed = True

        profile.save(
            update_fields=[
                "password_setup_completed",
                "updated_at",
            ]
        )

        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "portal:nickname_setup"
        )


# =========================================================
# Initial nickname setup
# =========================================================

@login_required
def nickname_setup(request):

    profile, _ = UserProfile.objects.get_or_create(
        user=request.user
    )

    if not profile.password_setup_completed:
        return redirect(
            "portal:password_setup"
        )


    if profile.nickname_setup_completed:
        return redirect_after_signup(request)


    if request.method == "POST":

        form = NicknameForm(
            request.POST,
            instance=profile,
        )

        if form.is_valid():

            profile = form.save(
                commit=False
            )

            profile.nickname_setup_completed = True

            profile.save()

            return redirect_after_signup(request)

    else:

        form = NicknameForm(
            instance=profile
        )

    return render(
        request,
        "portal/nickname_setup.html",
        {
            "form": form,
            "profile": profile,
        },
    )


# =========================================================
# Initial app setup
# =========================================================


@login_required
def app_setup(request):
    """
    旧アプリ選択URLとの互換性を維持。
    アプリ選択は廃止。
    """

    profile, _ = UserProfile.objects.get_or_create(
        user=request.user
    )

    setup_redirect = redirect_to_setup_if_needed(profile)

    if setup_redirect:
        return redirect(setup_redirect)

    return redirect("portal:home")




# =========================================================
# My Account
# =========================================================

@login_required
def manage_apps(request):

    profile, _ = UserProfile.objects.get_or_create(
        user=request.user
    )

    # =====================================================
    # Initial setup
    # =====================================================

    setup_redirect = redirect_to_setup_if_needed(
        profile
    )

    if setup_redirect:
        return redirect(setup_redirect)

    # =====================================================
    # Nickname form
    # =====================================================

    nickname_form = NicknameForm(
        instance=profile
    )

    # =====================================================
    # POST
    # =====================================================

    if request.method == "POST":

        form_type = request.POST.get(
            "form_type",
            "",
        )

        # ---------------------------------------------
        # Nickname
        # ---------------------------------------------

        if form_type == "nickname":

            nickname_form = NicknameForm(
                request.POST,
                instance=profile,
            )

            if nickname_form.is_valid():

                nickname_form.save()

                messages.success(
                    request,
                    "ニックネームを保存しました。",
                )

                return redirect(
                    "portal:manage_apps"
                )

        # ---------------------------------------------
        # Theme
        # ---------------------------------------------

        elif form_type == "theme":

            theme = request.POST.get(
                "theme_preference",
                "",
            )

            valid_themes = {
                "system",
                "light",
                "dark",
            }

            if theme not in valid_themes:

                messages.error(
                    request,
                    "有効な表示テーマを選択してください。",
                )

            else:

                profile.theme_preference = theme

                profile.save(
                    update_fields=[
                        "theme_preference",
                        "updated_at",
                    ]
                )

                messages.success(
                    request,
                    "表示テーマを保存しました。",
                )

                return redirect(
                    "portal:manage_apps"
                )

        else:

            messages.error(
                request,
                "無効な操作です。",
            )

    # =====================================================
    # Render
    # =====================================================

    return render(
        request,
        "portal/manage_apps.html",
        {
            "profile": profile,
            "nickname_form": nickname_form,
            "can_view_analytics": can_view_analytics(request.user),
        },
    )



# =========================================================
# Public Portal Home
# =========================================================

PORTAL_SEASONS = {key for key, _ in PortalSettings.SEASON_CHOICES} - {"auto"}


def portal_season(today):
    """日付から、Yappトップの季節デザインを決める。"""

    if today.month == 10 and today.day >= 15:
        return "halloween"
    if (today.month == 11 and today.day >= 20) or today.month in (12, 1, 2):
        return "winter"
    if today.month in (3, 4, 5):
        return "spring"
    if today.month in (6, 7, 8):
        return "summer"
    return "autumn"


def portal_latest_news(limit=3):
    """ニュースカードに出す最新の見出し。"""

    from news.services.deduplicator import ready_articles

    return list(
        ready_articles()
        .filter(duplicate_of__isnull=True)
        .order_by("-published_at")[:limit]
    )


def portal_card_photo(key):
    """
    static/portal/images/cards/<key>.jpg (または .webp) を置くと、
    アプリカードの背景が写真になる。なければイラストのまま。
    """

    from django.contrib.staticfiles import finders
    from django.templatetags.static import static

    for extension in ("webp", "jpg"):
        path = f"portal/images/cards/{key}.{extension}"
        if finders.find(path):
            return static(path)
    return ""


def home(request):
    """季節で表情が変わる、公開Yappポータル。"""
    from zoneinfo import ZoneInfo

    from django.templatetags.static import static

    # DjangoのTIME_ZONE設定にかかわらず、スイス現地の日付を使う。
    today = timezone.localtime(
        timezone.now(), ZoneInfo("Europe/Zurich")
    ).date()
    season = PortalSettings.load().season
    if season not in PORTAL_SEASONS:
        season = portal_season(today)

    # True にするとカードに「開発版をのぞく」リンクが出る。
    OUTINGS_PREVIEW_ENABLED = False

    featured_apps = [
        {
            "key": "news",
            "name": "Swiss News",
            "icon_url": static("pwa/news/icon-192.png"),
            "badge": "公開中",
            "status_class": "live",
            "eyebrow": "SWISS NEWS",
            "headline": "日本語でスイスの出来事を把握しよう。",
            "description": "スイスのニュースや暮らしに役立つ情報を、日本語で。毎日の情報収集をもっと身近に。",
            "url": reverse("news:home"),
            "action": "今すぐ読む",
            "features": ["ニュース", "暮らしのお知らせ"],
        },
        {
            "key": "washoku",
            "name": "スイスで和食",
            "icon_url": static("pwa/washoku/icon-192.png"),
            "badge": "まもなく公開",
            "status_class": "soon",
            "eyebrow": "WASHOKU",
            "headline": "スイスの台所に、みんなの知恵を。",
            "description": "レシピも、食材の買い方も、みんなの工夫も。スイスで楽しむ和食をもっと豊かに。",
            "url": reverse("washoku:home"),
            "action": "ひと足先にのぞく",
            "features": ["レシピ", "食材情報", "みんなの投稿"],
        },
        {
            "key": "outings",
            "name": "お出かけ",
            "icon_url": static("pwa/outings/icon-192.png"),
            "badge": "絶賛準備中",
            "status_class": "building",
            "eyebrow": "OUTINGS",
            "headline": "次のお休み、どこへ行こう？",
            "description": "季節のイベントや、ちょっと出かけたくなる場所。お出かけのアイデアを準備中。",
            "url": reverse("outings:home") if OUTINGS_PREVIEW_ENABLED else None,
            "action": "開発版をのぞく",
            "features": ["週末イベント", "季節の楽しみ", "お出かけ情報"],
        },
    ]

    for app in featured_apps:
        app["photo_url"] = portal_card_photo(app["key"])

    other_apps = [
        {
            "key": "games",
            "name": "ミニゲーム",
            "icon": "🎮",
            "description": "ちょっとした空き時間に遊べるゲーム。",
            "url": reverse("games:game_list"),
        },
        {
            "key": "colorcheck",
            "name": "色判定",
            "icon": "🎨",
            "description": "色覚異常の方のお助けアプリ。気になる色を簡単に確認。",
            "url": reverse("colorcheck:index"),
        },
        {
            "key": "events",
            "name": "イベント調整",
            "icon": "📅",
            "description": "みんなの予定を簡単に調整。",
            "url": reverse("event_scheduler:event_list"),
        },
        {
            "key": "board",
            "name": "暮らしの掲示板",
            "icon": "💬",
            "description": "生活の知恵や口コミを、みんなで。",
            "url": None,
            "badge": "準備中",
        },
    ]

    return render(
        request,
        "portal/home.html",
        {
            "season": season,
            "latest_news": portal_latest_news(),
            "featured_apps": featured_apps,
            "other_apps": other_apps,
            "announcements": list(PortalAnnouncement.current()),
            "idea_sent": request.GET.get("idea") == "sent",
        },
    )


@require_POST
def send_app_idea(request):
    """Yappトップの「アイデア募集」フォーム。保存して管理者にメールする。"""

    idea_text = (request.POST.get("idea") or "").strip()[:1000]
    contact = (request.POST.get("contact") or "").strip()[:200]

    # website はボット対策の見えない項目。入力されていたら保存しない。
    if idea_text and not request.POST.get("website"):
        idea = AppIdea.objects.create(
            idea=idea_text,
            contact=contact,
            user=request.user if request.user.is_authenticated else None,
        )
        recipient = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", "")
        if recipient:
            send_mail(
                subject="【Yapp】アプリのアイデアが届きました",
                message=(
                    f"{idea.idea}\n\n"
                    f"お名前・連絡先：{idea.contact or 'なし'}\n"
                    f"アカウント：{idea.user or 'ログインなし'}\n\n"
                    "Yapp Adminの「アプリのアイデア」から確認できます。"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=True,
            )

    return redirect(reverse("portal:home") + "?idea=sent#ideas")


# =========================================================
# Delete account
# =========================================================

@login_required
def delete_account(request):

    # 管理者アカウントの誤削除防止
    if request.user.is_superuser:
        messages.error(
            request,
            "管理者アカウントはこの画面から削除できません。",
        )

        return redirect(
            "portal:manage_apps"
        )


    if request.method == "POST":

        password = request.POST.get(
            "password",
            "",
        )


        if not request.user.check_password(
            password
        ):

            messages.error(
                request,
                "パスワードが正しくありません。",
            )

            return render(
                request,
                "portal/delete_account.html",
            )


        user = request.user


        # セッションを先に終了
        logout(
            request
        )


        # UserにCASCADEされている関連データも削除
        user.delete()


        return redirect(
            "news:home"
        )


    return render(
        request,
        "portal/delete_account.html",
    )


# =========================================================
# App access request
# =========================================================

@login_required
def request_app_access(request):

    if request.method != "POST":

        return redirect(
            "portal:home"
        )


    app_key = request.POST.get(
        "app_key",
        "",
    )

    requested_path = request.POST.get(
        "requested_path",
        "",
    )[:500]


    allowed_keys = {
        value
        for value, label
        in AppAccessRequest.AppKey.choices
    }


    if app_key not in allowed_keys:

        messages.error(
            request,
            "利用リクエストを送信できませんでした。",
        )

        return redirect(
            "portal:home"
        )


    access_request, created = (
        AppAccessRequest.objects.get_or_create(
            user=request.user,
            app_key=app_key,
            defaults={
                "requested_path": requested_path,
            },
        )
    )


    if created:

        messages.success(
            request,
            "利用リクエストを送信しました。",
        )


    elif (
        access_request.status
        == AppAccessRequest.Status.PENDING
    ):

        messages.info(
            request,
            "このアプリの利用リクエストはすでに送信済みです。",
        )


    else:

        access_request.status = (
            AppAccessRequest.Status.PENDING
        )

        access_request.requested_path = (
            requested_path
        )

        access_request.save(
            update_fields=[
                "status",
                "requested_path",
                "updated_at",
            ]
        )

        messages.success(
            request,
            "利用リクエストを再送しました。",
        )


    # 元のアプリページへ戻す
    if (
        requested_path.startswith("/")
        and not requested_path.startswith("//")
    ):

        return redirect(
            requested_path
        )


    return redirect(
        "portal:home"
    )


# =========================================================
# Password Change Done
# =========================================================

class YappPasswordChangeDoneView(
    auth_views.PasswordChangeDoneView
):

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        next_url = self.request.GET.get(
            "next", ""
        )

        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):

            context["return_url"] = next_url

        else:

            context["return_url"] = reverse(
                "portal:home"
            )

        return context