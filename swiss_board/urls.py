from django.urls import path

from . import views


app_name = "swiss_board"


urlpatterns = [

    path(
        "",
        views.home,
        name="home",
    ),

    path(
        "search/",
        views.post_search,
        name="search",
    ),

    path(
        "categories/",
        views.category_menu,
        name="categories",
    ),

    path(
        "mypage/",
        views.my_page,
        name="my_page",
    ),

    path(
        "mypage/profile/",
        views.profile_edit,
        name="profile_edit",
    ),

    path(
        "mypage/notifications/",
        views.my_notifications,
        name="my_notifications",
    ),

    path(
        "mypage/notifications/<int:pk>/open/",
        views.notification_open,
        name="notification_open",
    ),

    path(
        "my-posts/",
        views.my_posts,
        name="my_posts",
    ),

    path(
        "my-comments/",
        views.my_comments,
        name="my_comments",
    ),

    path(
        "posts/<int:pk>/comments/new/",
        views.comment_create,
        name="comment_create",
    ),

    path(
        "posts/new/",
        views.post_create,
        name="post_create",
    ),

    path(
        "posts/<int:pk>/edit/",
        views.post_edit,
        name="post_edit",
    ),

    path(
        "posts/<int:pk>/delete/",
        views.post_delete,
        name="post_delete",
    ),

    path(
        "posts/<int:pk>/",
        views.post_detail,
        name="post_detail",
    ),

    path(
        "comments/<int:pk>/edit/",
        views.comment_edit,
        name="comment_edit",
    ),

    path(
        "comments/<int:pk>/delete/",
        views.comment_delete,
        name="comment_delete",
    ),

    path(
        "my-questions/",
        views.my_questions,
        name="my_questions",
    ),

]

# =========================================================
# 404 Handler
# =========================================================

def custom_404(request, exception):

    if request.path.startswith("/swiss-board/"):

        from swiss_board.views import page_not_found

        return page_not_found(
            request,
            exception,
        )

    from django.views.defaults import page_not_found

    return page_not_found(
        request,
        exception,
    )


handler404 = custom_404