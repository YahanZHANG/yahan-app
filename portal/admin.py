from django.contrib import admin
from django.shortcuts import redirect

from .models import (
    AppAccessRequest,
    AppIdea,
    PortalAnnouncement,
    PortalAppPreference,
    PortalSettings,
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
