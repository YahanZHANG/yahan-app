from django.db.models import Count
from board.models import BoardPost
from board.permissions import can_post_board

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.shortcuts import redirect, render
from django.urls import reverse
from usage_analytics.permissions import can_view_analytics

from feeding.models import BabyMembership
from travel.models import UserProfile

from .forms import (
    AppSelectionForm,
    NicknameForm,
)
from .models import PortalAppPreference


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
}


# =========================================================
# Helpers
# =========================================================

def ensure_app_preferences(user):
    """
    ユーザーに6アプリ分の設定が存在しなければ作成する。
    """

    for index, (app_key, label) in enumerate(
        PortalAppPreference.AppKey.choices
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

        form = AppSelectionForm(
            request.POST
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

        form = AppSelectionForm(
            initial={
                "apps": all_app_keys,
            }
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

    allowed_keys = [
        value
        for value, label
        in PortalAppPreference.AppKey.choices
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
            user=request.user
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

    preferences = (
        PortalAppPreference
        .objects
        .filter(
            user=request.user,
            is_visible=True,
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
    # Board - Latest posts
    # =====================================================

    board_posts = (
        BoardPost.objects
        .select_related("author")
        .annotate(
            comment_count=Count("comments")
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

        "profile": profile,

        "nickname_form": nickname_form,

        "visible_apps": visible_apps,

        # 掲示板

        "board_posts": board_posts,

        "can_post_board": can_post_board(
            request.user
        ),

    }

    return render(
        request,
        "portal/home.html",
        context,
    )