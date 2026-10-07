from django.contrib import admin

from .models import (
    AppAccessRequest,
    PortalAppPreference,
)


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