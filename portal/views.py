from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
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
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import (
    force_bytes,
    force_str,
)
from django.utils.http import (
    urlsafe_base64_decode,
    urlsafe_base64_encode,
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
    PortalAppPreference,
)

from django.db.models import Q

from chat.models import (
    ChatMessage,
    ChatConnection,
)


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
    初回セットアップが終わっていなければ
    適切な画面名を返す。
    """

    if not profile.password_setup_completed:
        return "portal:password_setup"

    if not profile.nickname_setup_completed:
        return "portal:nickname_setup"

    if not profile.app_setup_completed:
        return "portal:app_setup"

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

def signup(request):

    if request.user.is_authenticated:

        return redirect(
            "portal:home"
        )

    if request.method == "POST":

        form = SignupForm(
            request.POST
        )

        if form.is_valid():

            # =================================================
            # Create inactive user
            # =================================================

            user = form.save(
                commit=False
            )

            user.email = (
                form.cleaned_data[
                    "email"
                ]
            )

            # メール確認が終わるまでは
            # ログインできない状態にする
            user.is_active = False

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

            # メール認証後に設定
            profile.nickname_setup_completed = False
            profile.app_setup_completed = False

            profile.save()


            # =================================================
            # Email verification
            # =================================================

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
                "アカウント登録ありがとうございます。\n"
                "以下のリンクを開いて、"
                "メールアドレスを確認してください。\n\n"
                f"{verification_url}\n\n"
                "このメールに心当たりがない場合は、"
                "そのまま破棄してください。\n\n"
                "Yapp @ 2026"
            )

            try:

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=(
                        settings.DEFAULT_FROM_EMAIL
                    ),
                    recipient_list=[
                        user.email
                    ],
                    fail_silently=False,
                )

            except Exception:

                # メール送信に失敗した場合、
                # 使えない未認証アカウントを残さない
                user.delete()

                form.add_error(
                    None,
                    (
                        "確認メールを送信できませんでした。"
                        "時間をおいてもう一度お試しください。"
                    ),
                )

            else:

                return render(
                    request,
                    "registration/signup_email_sent.html",
                    {
                        "email": user.email,
                    },
                )

    else:

        form = SignupForm()

    return render(
        request,
        "registration/signup.html",
        {
            "form": form,
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


    return redirect(
        "portal:nickname_setup"
    )

# =========================================================
# Normal password change
# =========================================================

class PortalPasswordChangeView(
    auth_views.PasswordChangeView
):
    template_name = (
        "registration/password_change_form.html"
    )

    def get_success_url(self):
        return reverse(
            "password_change_done"
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

    def dispatch(
        self,
        request,
        *args,
        **kwargs,
    ):
        if request.user.is_authenticated:

            profile, _ = (
                UserProfile.objects.get_or_create(
                    user=request.user
                )
            )

            if profile.password_setup_completed:

                if not profile.nickname_setup_completed:
                    return redirect(
                        "portal:nickname_setup"
                    )

                if not profile.app_setup_completed:
                    return redirect(
                        "portal:app_setup"
                    )

                return redirect(
                    "portal:home"
                )

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

        if not profile.app_setup_completed:
            return redirect(
                "portal:app_setup"
            )

        return redirect(
            "portal:home"
        )

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

            return redirect(
                "portal:app_setup"
            )

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

    profile, _ = UserProfile.objects.get_or_create(
        user=request.user
    )

    if not profile.password_setup_completed:
        return redirect(
            "portal:password_setup"
        )

    if not profile.nickname_setup_completed:
        return redirect(
            "portal:nickname_setup"
        )

    if profile.app_setup_completed:
        return redirect(
            "portal:home"
        )

    all_app_keys = [
        value
        for value, label
        in PortalAppPreference.AppKey.choices
    ]

    if request.method == "POST":

        available_choices = (
            get_app_choices_for_user(
                request.user
            )
        )

        form = AppSelectionForm(
            request.POST,
            choices=available_choices,
        )

        if form.is_valid():

            selected_apps = form.cleaned_data[
                "apps"
            ]

            for index, app_key in enumerate(
                all_app_keys
            ):

                is_visible = (
                    app_key in selected_apps
                )

                if is_visible:
                    display_order = (
                        selected_apps.index(
                            app_key
                        )
                    )
                else:
                    display_order = (
                        100 + index
                    )

                (
                    PortalAppPreference
                    .objects
                    .update_or_create(
                        user=request.user,
                        app_key=app_key,
                        defaults={
                            "is_visible": is_visible,
                            "display_order": (
                                display_order
                            ),
                        },
                    )
                )

            profile.app_setup_completed = True

            profile.save(
                update_fields=[
                    "app_setup_completed",
                    "updated_at",
                ]
            )

            messages.success(
                request,
                "初回設定が完了しました。",
            )

            return redirect(
                "portal:home"
            )

    else:

        available_choices = (
            get_app_choices_for_user(
                request.user
            )
        )

        available_keys = [
            value
            for value, label
            in available_choices
        ]

        form = AppSelectionForm(
            choices=available_choices,
            initial={
                "apps": available_keys,
            },
        )

    return render(
        request,
        "portal/app_setup.html",
        {
            "form": form,
            "profile": profile,
        },
    )


# =========================================================
# Manage apps and account settings
# =========================================================

@login_required
def manage_apps(request):

    profile, _ = UserProfile.objects.get_or_create(
        user=request.user
    )

    setup_redirect = redirect_to_setup_if_needed(
        profile
    )

    if setup_redirect:
        return redirect(
            setup_redirect
        )

    ensure_app_preferences(
        request.user
    )

    available_choices = (
        get_app_choices_for_user(
            request.user
        )
    )

    allowed_keys = [
        value
        for value, label
        in available_choices
    ]

    # =====================================================
    # Nickname form
    # =====================================================

    nickname_form = NicknameForm(
        instance=profile
    )

    # =====================================================
    # POST: Save nickname
    # =====================================================

    if (
        request.method == "POST"
        and request.POST.get("form_type") == "nickname"
    ):

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

    # =====================================================
    # POST: Save app preferences
    # =====================================================

    elif request.method == "POST":

        visible_keys = set(
            request.POST.getlist(
                "visible_apps"
            )
        )

        visible_keys = {
            key
            for key in visible_keys
            if key in allowed_keys
        }

        if not visible_keys:

            messages.error(
                request,
                "少なくとも1つのアプリを表示してください。",
            )

        else:

            raw_order = (
                request.POST
                .get(
                    "app_order",
                    "",
                )
                .split(",")
            )

            submitted_order = []

            for key in raw_order:

                if (
                    key in allowed_keys
                    and key not in submitted_order
                ):

                    submitted_order.append(
                        key
                    )

            # JavaScriptから一部送られなかった場合も
            # 残りのアプリを後ろに補完する

            ordered_keys = (
                submitted_order
                + [
                    key
                    for key in allowed_keys
                    if key not in submitted_order
                ]
            )

            for index, app_key in enumerate(
                ordered_keys
            ):

                (
                    PortalAppPreference
                    .objects
                    .update_or_create(

                        user=request.user,

                        app_key=app_key,

                        defaults={
                            "is_visible": (
                                app_key in visible_keys
                            ),
                            "display_order": index,
                        },

                    )
                )

            messages.success(
                request,
                "アプリの表示と順番を保存しました。",
            )

            return redirect(
                "portal:home"
            )

    # =====================================================
    # App preferences
    # =====================================================

    preferences = (
        PortalAppPreference
        .objects
        .filter(
            user=request.user,
            app_key__in=allowed_keys,
        )
        .order_by(
            "display_order",
            "id",
        )
    )

    apps = []

    for preference in preferences:

        config = APP_CONFIG.get(
            preference.app_key
        )

        if not config:
            continue

        apps.append(
            {
                "key": preference.app_key,

                "name": config["name"],

                "label": config["label"],

                "icon": config["icon"],

                "description": config["description"],

                "is_visible": (
                    preference.is_visible
                ),
            }
        )

    # =====================================================
    # Render
    # =====================================================

    return render(
        request,
        "portal/manage_apps.html",
        {
            "profile": profile,
            "apps": apps,
            "nickname_form": nickname_form,
        },
    )

# =========================================================
# Portal home
# =========================================================

@login_required
def home(request):

    profile, _ = UserProfile.objects.get_or_create(
        user=request.user
    )

    setup_redirect = redirect_to_setup_if_needed(
        profile
    )

    if setup_redirect:
        return redirect(
            setup_redirect
        )

    ensure_app_preferences(
        request.user
    )

    # =====================================================
    # Feeding permission
    # =====================================================

    can_use_feeding = (
        request.user.is_superuser
        or BabyMembership.objects.filter(
            user=request.user
        ).exists()
    )

    # =====================================================
    # Nickname edit
    # =====================================================

    if request.method == "POST":

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
                "portal:home"
            )

    else:

        nickname_form = NicknameForm(
            instance=profile
        )

    # =====================================================
    # Visible apps
    # =====================================================

    available_choices = (
        get_app_choices_for_user(
            request.user
        )
    )

    available_keys = [
        value
        for value, label
        in available_choices
    ]

    can_access_chat = (
        "chat" in available_keys
    )

    preferences = (
        PortalAppPreference
        .objects
        .filter(
            user=request.user,
            is_visible=True,
            app_key__in=available_keys,
        )
        .order_by(
            "display_order",
            "id",
        )
    )

    visible_apps = []

    for preference in preferences:

        # 離乳食アプリの利用権限がない場合は
        # Portalには表示しない
        if (
            preference.app_key == "feeding"
            and not can_use_feeding
        ):
            continue

        config = APP_CONFIG.get(
            preference.app_key
        )

        if not config:
            continue

        visible_apps.append(
            {
                "key": preference.app_key,
                "name": config["name"],
                "label": config["label"],
                "icon": config["icon"],
                "url": reverse(
                    config["url_name"]
                ),
                "card_class": (
                    config["card_class"]
                ),
                "icon_class": (
                    config["icon_class"]
                ),
            }
        )

    # =====================================================
    # Chat - Unread messages
    # =====================================================

    current_user = request.user

    # 承認済みの友達関係のみ取得

    accepted_connections = (
        ChatConnection.objects.filter(

            Q(user_low=current_user)
            |
            Q(user_high=current_user),

            status=ChatConnection.Status.ACCEPTED,

        )
    )

    # 友達のユーザーIDを取得
    # 数字IDは内部処理にのみ使用

    friend_ids = []

    for connection in accepted_connections:

        other_user = connection.other_user(
            current_user
        )

        if other_user.is_active:

            friend_ids.append(
                other_user.pk
            )

    # 友達から届いた未読メッセージ数

    unread_chat_count = (
        ChatMessage.objects.filter(

            recipient=current_user,

            sender_id__in=friend_ids,

            is_read=False,

        ).count()
    )

    # =====================================================
    # Board - Latest posts
    # =====================================================

    two_weeks_ago = (
        timezone.now()
        - timedelta(
            days=14
        )
    )


    board_posts = (
        BoardPost.objects
        .visible_to(
            request.user
        )
        .select_related(
            "author"
        )
        .annotate(
            comment_count=Count(
                "comments"
            )
        )
        .order_by(
            "-is_pinned",
            "-created_at",
        )[:3]
    )

    # =====================================================
    # Context
    # =====================================================

    context = {
        "can_use_feeding": can_use_feeding,
        "can_view_analytics": can_view_analytics(
            request.user
        ),
        "can_access_chat": can_access_chat,
        "profile": profile,
        "nickname_form": nickname_form,
        "visible_apps": visible_apps,

        # お知らせ
        "board_posts": board_posts,
        "can_post_board": can_post_board(
            request.user
        ),

        # Chat
        "unread_chat_count": unread_chat_count,

    }

    return render(
        request,
        "portal/home.html",
        context,
    )


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