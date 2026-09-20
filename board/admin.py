from django.contrib import admin

from .models import (
    BoardPost,
    BoardComment,
)


# =========================================================
# Board posts
# =========================================================

@admin.register(BoardPost)
class BoardPostAdmin(admin.ModelAdmin):

    list_display = [
        "title",
        "author",
        "is_pinned",
        "created_at",
    ]

    list_filter = [
        "is_pinned",
        "created_at",
    ]

    search_fields = [
        "title",
        "body",
        "author__username",
    ]

    list_editable = [
        "is_pinned",
    ]

    ordering = [
        "-is_pinned",
        "-created_at",
    ]


# =========================================================
# Board comments
# =========================================================

@admin.register(BoardComment)
class BoardCommentAdmin(admin.ModelAdmin):

    list_display = [
        "post",
        "author",
        "created_at",
    ]

    search_fields = [
        "body",
        "author__username",
        "post__title",
    ]

    list_filter = [
        "created_at",
    ]

    ordering = [
        "-created_at",
    ]