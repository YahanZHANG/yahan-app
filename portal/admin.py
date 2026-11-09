from django import forms
from django.contrib import admin
from django.shortcuts import redirect

from .models import (
    AppPopup,
    AppAccessRequest,
    AppIdea,
    PortalAnnouncement,
    PortalAppPreference,
    PortalSettings,
    PortalThemeText,
)


@admin.register(PortalAnnouncement)
class PortalAnnouncementAdmin(admin.ModelAdmin):

    list_display = [
        "message",
        "link",
        "is_active",
        "created_at",
    ]

    list_editable = [
        "is_active",
    ]


@admin.register(AppAccessRequest)
class AppAccessRequestAdmin(admin.ModelAdmin):

    list_display = [
        "user",
        "app_key",
        "status",
        "created_at",
    ]

    list_editable = [
        "status",
    ]

    list_filter = [
        "status",
        "app_key",
    ]

    search_fields = [
        "user__username",
        "user__email",
    ]

    ordering = [
        "-created_at",
    ]


    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):

        super().save_model(
            request,
            obj,
            form,
            change,
        )


        # PortalAppPreference に存在するアプリだけ同期する
        portal_app_keys = {
            value
            for value, label
            in PortalAppPreference.AppKey.choices
        }


        if obj.app_key not in portal_app_keys:
            return


        # =============================================
        # Approved
        # =============================================

        if (
            obj.status
            == AppAccessRequest.Status.APPROVED
        ):

            preference, created = (
                PortalAppPreference.objects.get_or_create(
                    user=obj.user,
                    app_key=obj.app_key,
                    defaults={
                        "is_visible": True,
                        "display_order": (
                            PortalAppPreference.objects
                            .filter(user=obj.user)
                            .count()
                        ),
                    },
                )
            )


            # すでに設定が存在していてOFFならONにする
            if not created and not preference.is_visible:

                preference.is_visible = True

                preference.save(
                    update_fields=[
                        "is_visible",
                        "updated_at",
                    ]
                )


        # =============================================
        # Not approved
        # =============================================

        else:

            PortalAppPreference.objects.filter(
                user=obj.user,
                app_key=obj.app_key,
            ).update(
                is_visible=False,
            )

@admin.register(AppIdea)
class AppIdeaAdmin(admin.ModelAdmin):

    list_display = [
        "idea",
        "contact",
        "user",
        "handled",
        "created_at",
    ]

    list_editable = [
        "handled",
    ]

    list_filter = [
        "handled",
    ]


@admin.register(PortalSettings)
class PortalSettingsAdmin(admin.ModelAdmin):
    """1件だけの設定。一覧を開くとすぐその設定の画面になる。"""

    def changelist_view(self, request, extra_context=None):
        settings_row = PortalSettings.load()
        return redirect("admin:portal_portalsettings_change", settings_row.pk)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PortalThemeText)
class PortalThemeTextAdmin(admin.ModelAdmin):
    """季節・イベントごとのキャッチ。一覧でそのまま書き換えられる。"""

    list_display = ["theme", "title", "headline"]
    list_editable = ["title", "headline"]
    list_display_links = ["theme"]
    readonly_fields = ["theme"]

    def changelist_view(self, request, extra_context=None):
        PortalThemeText.ensure_all()
        return super().changelist_view(request, extra_context)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class AppPopupAdminForm(forms.ModelForm):
    """ポップアップの画像は、URL を入れるほか、ここからアップロードもできる (Cloudinary)。"""

    image_upload = forms.FileField(
        label="画像をアップロード",
        required=False,
        help_text="小さく変換して保存し、上の「画像のURL」を置きかえます。消すときは「画像のURL」を空にします。",
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
    )

    class Meta:
        model = AppPopup
        fields = "__all__"

    def clean_image_upload(self):
        from django.core.exceptions import ValidationError

        from outings.services.user_event_cloudinary import upload_user_event_photo
        from outings.services.user_event_images import process_user_event_image

        photo = self.cleaned_data.get("image_upload")
        if not photo:
            return ""
        try:
            processed = process_user_event_image(photo, max_size=1200, quality=78)
            return upload_user_event_photo(processed, folder="yapp/popup", filename="popup.webp")
        except ValidationError as error:
            raise forms.ValidationError(error.messages)


@admin.register(AppPopup)
class AppPopupAdmin(admin.ModelAdmin):

    form = AppPopupAdminForm
    readonly_fields = ["image_preview"]

    list_display = ["title", "app", "is_active", "frequency", "audience", "order", "preview_link", "updated_at"]
    list_editable = ["is_active", "order"]
    list_filter = ["app", "is_active"]

    fieldsets = [
        (None, {"fields": ["app", "is_active"]}),
        ("中身", {"fields": ["emoji", "title", "body", "image_url", "image_upload", "image_preview", "button_label", "link", "open_in_browser"]}),
        ("出し方", {"fields": ["frequency", "audience", "home_only", "starts_at", "ends_at", "order"]}),
    ]

    @admin.display(description="画像（いま）")
    def image_preview(self, obj):
        from django.utils.html import format_html

        if not obj.image_url:
            return "なし"
        return format_html('<img src="{}" alt="" style="width:200px;max-height:140px;object-fit:cover;border-radius:8px">', obj.image_url)

    def save_model(self, request, obj, form, change):
        uploaded = form.cleaned_data.get("image_upload")
        if uploaded:
            obj.image_url = uploaded
        super().save_model(request, obj, form, change)

    @admin.display(description="プレビュー")
    def preview_link(self, obj):
        from django.utils.html import format_html

        path = "/" if obj.app == "top" else f"/{obj.app}/"
        return format_html('<a href="{}?popup_preview={}" target="_blank">見てみる</a>', path, obj.pk)
