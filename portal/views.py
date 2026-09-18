from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.shortcuts import redirect, render
from django.urls import reverse

from feeding.models import BabyMembership
from travel.models import UserProfile

from .forms import (
    AppSelectionForm,
    NicknameForm,
)
from .models import PortalAppPreference


# =========================================================
# 通常のパスワード変更
# =========================================================

class PortalPasswordChangeView(
    auth_views.PasswordChangeView
):
    """
    Portalから通常のパスワード変更を行う。

    通常変更では、
    現在のパスワードの入力が必要。
    """

    template_name = (
        "registration/password_change_form.html"
    )

    def get_success_url(self):
        return reverse(
            "password_change_done"
        )


# =========================================================
# 初回パスワード設定
# =========================================================

class InitialPasswordSetupView(
    auth_views.PasswordChangeView
):
    """
    初回ログイン専用。

    現在のパスワードは入力させず、
    新しいパスワードを2回入力して設定する。
    """

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

            # すでに初回パスワード設定が
            # 完了しているユーザーには、
            # 現在のパスワードなしで
            # 再設定させない。
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
# 初回ニックネーム設定
# =========================================================

@login_required
def nickname_setup(request):

    profile, _ = UserProfile.objects.get_or_create(
        user=request.user
    )

    # パスワード設定がまだなら
    # 先にパスワード設定へ
    if not profile.password_setup_completed:
        return redirect(
            "portal:password_setup"
        )

    # すでにニックネーム設定済み
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
# 初回アプリ選択
# =========================================================

@login_required
def app_setup(request):

    profile, _ = UserProfile.objects.get_or_create(
        user=request.user
    )

    # パスワード設定がまだ
    if not profile.password_setup_completed:
        return redirect(
            "portal:password_setup"
        )

    # ニックネーム設定がまだ
    if not profile.nickname_setup_completed:
        return redirect(
            "portal:nickname_setup"
        )

    # 初回設定完了済み
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

        # 初期状態では
        # 6アプリすべて選択済みにする
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
# Portal home
# =========================================================

@login_required
def home(request):

    profile, _ = UserProfile.objects.get_or_create(
        user=request.user
    )

    # =====================================================
    # 初回セットアップ
    # =====================================================

    if not profile.password_setup_completed:
        return redirect(
            "portal:password_setup"
        )

    if not profile.nickname_setup_completed:
        return redirect(
            "portal:nickname_setup"
        )

    if not profile.app_setup_completed:
        return redirect(
            "portal:app_setup"
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

    context = {
        "can_use_feeding": can_use_feeding,
        "profile": profile,
        "nickname_form": nickname_form,
    }

    return render(
        request,
        "portal/home.html",
        context,
    )