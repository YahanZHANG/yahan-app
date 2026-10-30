"""
管理画面全体の検索。Admin に登録されたすべての一覧 (検索できるもの) から、まとめて探す。
"""

from urllib.parse import urlencode

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse

from portal.templatetags.yapp_admin import RARE_APPS, SEARCH_SKIP, yapp_split_apps


# 1つの一覧から出す件数
RESULTS_PER_LIST = 5


def search_list(request, model_admin, query):
    """1つの一覧の検索結果: (件数, 先頭の数件)。検索できない一覧は None"""

    if not model_admin.search_fields or not model_admin.has_view_permission(request):
        return None

    queryset = model_admin.get_queryset(request)
    queryset, may_have_duplicates = model_admin.get_search_results(request, queryset, query)

    if may_have_duplicates:
        queryset = queryset.distinct()

    count = queryset.count()

    if not count:
        return None

    return count, list(queryset[:RESULTS_PER_LIST])


@staff_member_required
def admin_search(request):

    query = request.GET.get("q", "").strip()
    groups = []
    total = 0

    if query:

        apps = yapp_split_apps(admin.site.get_app_list(request))

        for app in apps["main"] + apps["rare"]:
            for entry in app["models"]:

                model = entry["model"]

                if (app["app_label"], entry["object_name"]) in SEARCH_SKIP:
                    continue
                model_admin = admin.site._registry.get(model)
                found = search_list(request, model_admin, query) if model_admin else None

                if not found:
                    continue

                count, objects = found
                opts = model._meta
                items = []

                for obj in objects:
                    try:
                        url = reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk])
                    except NoReverseMatch:
                        url = ""
                    items.append({"label": str(obj)[:90] or f"#{obj.pk}", "url": url})

                total += count
                groups.append({
                    "app": app["name"],
                    "name": entry["name"],
                    "count": count,
                    "items": items,
                    "more_url": (entry.get("admin_url") or "") + "?" + urlencode({"q": query}),
                    "rare": app["app_label"] in RARE_APPS,
                })

    context = {
        **admin.site.each_context(request),
        "title": f"「{query}」の検索結果" if query else "管理画面をまとめて検索",
        "query": query,
        "groups": groups,
        "total": total,
    }

    return render(request, "admin/yapp_search.html", context)
