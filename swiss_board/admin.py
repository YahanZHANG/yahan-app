from django.contrib import admin

from .models import SwissBoardPost


@admin.register(SwissBoardPost)
class SwissBoardPostAdmin(admin.ModelAdmin):

    list_display = [
        "id",
        "title",
        "author",
        "category",
        "region",
        "status",
        "created_at",
    ]

    list_display_links = [
        "id",
        "title",
    ]

    list_filter = [
        "status",
        "category",
        "created_at",
    ]

    search_fields = [
        "title",
        "body",
        "region",
        "author__username",
        "author__email",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]

    autocomplete_fields = []

    ordering = [
        "-created_at",
        "-id",
    ]

    list_per_page = 30

    fieldsets = [

        (
            "投稿内容",
            {
                "fields": [
                    "author",
                    "title",
                    "body",
                    "category",
                    "subcategory",
                    "region",
                ],
            },
        ),

        (
            "公開設定",
            {
                "fields": [
                    "status",
                ],
            },
        ),

        (
            "日時",
            {
                "fields": [
                    "created_at",
                    "updated_at",
                ],
            },
        ),

    ]