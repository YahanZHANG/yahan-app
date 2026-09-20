from django.contrib import messages

from django.contrib.auth.decorators import (
    login_required,
)

from django.core.paginator import Paginator

from django.db.models import Count

from django.http import (
    HttpResponseForbidden,
)

from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from django.views.decorators.http import (
    require_POST,
)

from .forms import (
    BoardPostForm,
    BoardCommentForm,
)

from .models import (
    BoardPost,
    BoardComment,
)

from .permissions import (
    can_post_board,
    can_manage_post,
    can_delete_comment,
)


# =========================================================
# Board post list
# =========================================================

@login_required
def post_list(request):

    posts = (
        BoardPost.objects
        .select_related("author")
        .annotate(
            comment_count=Count("comments")
        )
        .order_by(
            "-is_pinned",
            "-created_at",
        )
    )

    paginator = Paginator(
        posts,
        10,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    return render(
        request,
        "board/post_list.html",
        {
            "page_obj": page_obj,
            "can_post_board": can_post_board(
                request.user
            ),
        },
    )


# =========================================================
# Board post detail / Add comment
# =========================================================

@login_required
def post_detail(request, pk):

    post = get_object_or_404(
        BoardPost.objects.select_related(
            "author"
        ),
        pk=pk,
    )

    comments = (
        post.comments
        .select_related("author")
        .order_by("created_at")
    )

    # =====================================================
    # Add comment
    # =====================================================

    if request.method == "POST":

        comment_form = BoardCommentForm(
            request.POST
        )

        if comment_form.is_valid():

            comment = comment_form.save(
                commit=False
            )

            comment.post = post

            comment.author = request.user

            comment.save()

            messages.success(
                request,
                "コメントを投稿しました。",
            )

            return redirect(
                "board:post_detail",
                pk=post.pk,
            )

    else:

        comment_form = BoardCommentForm()

    return render(
        request,
        "board/post_detail.html",
        {
            "post": post,
            "comments": comments,
            "comment_form": comment_form,

            "can_manage_post": can_manage_post(
                request.user,
                post,
            ),
        },
    )


# =========================================================
# Create post
# =========================================================

@login_required
def post_create(request):

    if not can_post_board(
        request.user
    ):

        return HttpResponseForbidden(
            "投稿権限がありません。"
        )

    if request.method == "POST":

        form = BoardPostForm(
            request.POST
        )

        if form.is_valid():

            post = form.save(
                commit=False
            )

            post.author = request.user

            post.save()

            messages.success(
                request,
                "お知らせを投稿しました。",
            )

            return redirect(
                "board:post_detail",
                pk=post.pk,
            )

    else:

        form = BoardPostForm()

    return render(
        request,
        "board/post_form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


# =========================================================
# Edit post
# =========================================================

@login_required
def post_edit(request, pk):

    post = get_object_or_404(
        BoardPost,
        pk=pk,
    )

    if not can_manage_post(
        request.user,
        post,
    ):

        return HttpResponseForbidden(
            "編集権限がありません。"
        )

    if request.method == "POST":

        form = BoardPostForm(
            request.POST,
            instance=post,
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                "お知らせを更新しました。",
            )

            return redirect(
                "board:post_detail",
                pk=post.pk,
            )

    else:

        form = BoardPostForm(
            instance=post
        )

    return render(
        request,
        "board/post_form.html",
        {
            "form": form,
            "is_edit": True,
            "post": post,
        },
    )


# =========================================================
# Delete post
# =========================================================

@login_required
@require_POST
def post_delete(request, pk):

    post = get_object_or_404(
        BoardPost,
        pk=pk,
    )

    if not can_manage_post(
        request.user,
        post,
    ):

        return HttpResponseForbidden(
            "削除権限がありません。"
        )

    post.delete()

    messages.success(
        request,
        "お知らせを削除しました。",
    )

    return redirect(
        "board:post_list"
    )


# =========================================================
# Delete comment
# =========================================================

@login_required
@require_POST
def comment_delete(request, pk):

    comment = get_object_or_404(
        BoardComment,
        pk=pk,
    )

    if not can_delete_comment(
        request.user,
        comment,
    ):

        return HttpResponseForbidden(
            "コメントの削除権限がありません。"
        )

    post_pk = comment.post_id

    comment.delete()

    messages.success(
        request,
        "コメントを削除しました。",
    )

    return redirect(
        "board:post_detail",
        pk=post_pk,
    )