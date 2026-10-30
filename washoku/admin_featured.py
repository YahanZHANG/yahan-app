"""
管理画面の「注目の管理」: HOMEの「注目」に出ているものの一覧と、外す・足す・戻すを1ページで。
"""

from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .models import Comment, Post
from .views import FEATURED_DAYS, WEEKLY_FEATURED_COUNT, featured_items, public_comment_targets


# 候補として並べる数
CANDIDATE_COUNT = 30


def row(kind, item, stamps=None):
    """一覧の1行: 種類・見出し・どこへの投稿か・リンク"""

    if kind == "post":
        label = item.title
        kind_label = item.get_kind_display()
        place = ""
        admin_url = reverse("admin:washoku_post_change", args=[item.pk])
    else:
        label = item.body
        kind_label = "返信" if item.parent_id else item.get_kind_display()
        place = item.target.name if item.target else ""
        admin_url = reverse("admin:washoku_comment_change", args=[item.pk])

    return {
        "kind": kind,
        "item": item,
        "label": label,
        "kind_label": kind_label,
        "place": place,
        "stamps": stamps,
        "url": item.get_absolute_url(),
        "admin_url": admin_url,
    }


def visible_comments():
    return (
        Comment.objects
        .filter(is_hidden=False, is_deleted=False)
        .filter(public_comment_targets())
        .select_related("recipe", "ingredient", "store", "post", "author")
    )


def visible_posts():
    return Post.objects.filter(status="published").exclude(kind="board").select_related("author")


@staff_member_required
def featured_admin(request):

    if request.method == "POST":
        return featured_action(request)

    since = timezone.now() - timedelta(days=FEATURED_DAYS)
    query = request.GET.get("q", "").strip()[:100]

    # いま HOME の「注目」に出ているもの (出る順)
    showing = [
        row(entry["kind"], entry["item"], entry["count"])
        for entry in featured_items(limit=WEEKLY_FEATURED_COUNT)
    ]
    showing_keys = {(entry["kind"], entry["item"].pk) for entry in showing}

    # 手で選んだもの (出る数より多ければ、順番の後ろのものは出ていない)
    picked = [row("post", post) for post in visible_posts().filter(is_featured=True)]
    picked += [row("comment", comment) for comment in visible_comments().filter(is_featured=True)]
    picked.sort(key=lambda entry: (entry["item"].featured_order, -entry["item"].created_at.timestamp()))

    # 候補: 最近の投稿・コメント (スタンプの多い順)。言葉で探すと、古いものも探せる
    posts = visible_posts().filter(is_featured=False)
    comments = visible_comments().filter(is_featured=False)

    if query:
        posts = posts.filter(Q(title__icontains=query) | Q(body__icontains=query))
        comments = comments.filter(body__icontains=query)
    else:
        posts = posts.filter(created_at__gte=since)
        comments = comments.filter(created_at__gte=since)

    stamp_filter = Q(reactions__created_at__gte=since)
    posts = posts.annotate(stamp_count=Count("reactions", filter=stamp_filter)).order_by("-stamp_count", "-created_at")[:CANDIDATE_COUNT]
    comments = comments.annotate(stamp_count=Count("reactions", filter=stamp_filter)).order_by("-stamp_count", "-created_at")[:CANDIDATE_COUNT]

    candidates = [row("post", post, post.stamp_count) for post in posts]
    candidates += [row("comment", comment, comment.stamp_count) for comment in comments]
    candidates.sort(key=lambda entry: (entry["stamps"] or 0, entry["item"].created_at), reverse=True)
    candidates = candidates[:CANDIDATE_COUNT]

    for entry in candidates + picked:
        entry["showing"] = (entry["kind"], entry["item"].pk) in showing_keys

    hidden = [row("post", post) for post in visible_posts().filter(featured_hidden=True)]
    hidden += [row("comment", comment) for comment in visible_comments().filter(featured_hidden=True)]

    return render(
        request,
        "admin/washoku/featured.html",
        {
            "title": "注目の管理",
            "showing": showing,
            "picked": picked,
            "candidates": candidates,
            "hidden": hidden,
            "query": query,
            "limit": WEEKLY_FEATURED_COUNT,
            "days": FEATURED_DAYS,
        },
    )


def featured_action(request):

    kind = request.POST.get("kind")
    model = {"post": Post, "comment": Comment}.get(kind)
    pk = request.POST.get("pk", "")

    if model is None or not pk.isdecimal():
        messages.error(request, "うまく操作できませんでした。")
        return redirect("washoku_featured_admin")

    item = get_object_or_404(model, pk=int(pk))
    op = request.POST.get("op")

    if op == "add":
        # 足したものは、いま手で選んでいるものの後ろに並べる
        item.is_featured = True
        item.featured_hidden = False
        orders = [
            model.objects.filter(is_featured=True).aggregate(last=Max("featured_order"))["last"] or 0
            for model in (Post, Comment)
        ]
        item.featured_order = min(max(orders) + 1, 999)
        message = "注目に足しました。"
    elif op == "remove":
        # 手で選んだのを外すだけでなく、スタンプで自動に出ることもないようにする
        item.is_featured = False
        item.featured_hidden = True
        message = "注目から外しました。"
    elif op == "restore":
        item.featured_hidden = False
        message = "外したのを戻しました。スタンプが多ければ、また自動で注目に出ます。"
    elif op == "order" and request.POST.get("order", "").isdecimal():
        item.featured_order = min(int(request.POST["order"]), 999)
        message = "順番を変えました。"
    else:
        messages.error(request, "うまく操作できませんでした。")
        return redirect("washoku_featured_admin")

    item.save(update_fields=["is_featured", "featured_hidden", "featured_order"])
    messages.success(request, message)

    back = request.POST.get("q", "")
    url = reverse("washoku_featured_admin")
    return redirect(f"{url}?{urlencode({'q': back})}" if back else url)
