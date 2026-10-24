"""
人気ページの一覧で、URLの代わりに「どのページか」が分かる名前を出す。
"""

import logging

from django.apps import apps
from django.urls import Resolver404, resolve


logger = logging.getLogger(__name__)


# url名 -> (モデル, URLの引数, 名前の項目, 引数をどの項目で探すか)
DETAIL_PAGES = {
    "washoku:recipe_detail": ("washoku.Recipe", "pk", "name", "pk"),
    "washoku:ingredient_detail": ("washoku.Ingredient", "pk", "name", "pk"),
    "washoku:store_detail": ("washoku.Store", "pk", "name", "pk"),
    "washoku:post_detail": ("washoku.Post", "pk", "title", "pk"),
    "outings:event_detail": ("outings.Event", "pk", "title", "pk"),
    "outings:tourist_spot_detail": ("outings.TouristSpot", "pk", "title_ja", "pk"),
    "news:topic_detail": ("news.Topic", "slug", "name", "slug"),
    "news:region_detail": ("news.Region", "slug", "name", "slug"),
    "news:source_detail": ("news.NewsSource", "source_id", "name", "pk"),
}

PAGE_NAMES = {
    "portal:home": "トップ",
    "portal:support": "サポートページ",
    "portal:signup": "新規登録",
    "login": "ログイン",
    "news:home": "ホーム",
    "news:topic_list": "トピック一覧",
    "news:favorites": "お気に入り",
    "news:settings": "設定",
    "news:about": "このアプリについて",
    "news:services": "サービス一覧",
    "news:digest_list": "まとめ",
    "news_push_settings": "通知設定",
    "outings:home": "ホーム",
    "outings:event_home": "イベント一覧",
    "outings:search": "検索",
    "outings:about_outings": "このアプリについて",
    "outings:tourist_spot_list": "旅行先一覧",
    "outings:saved_all": "お気に入り",
    "washoku:home": "ホーム",
    "washoku:recipe_list": "レシピ一覧",
    "washoku:find_by_mood": "気分で選ぶ",
    "washoku:find_by_ingredients": "食材で選ぶ",
    "washoku:random_recipe": "おまかせ",
    "washoku:ingredient_list": "食材一覧",
    "washoku:store_list": "お店一覧",
    "washoku:about": "このアプリについて",
    "washoku:my_page": "マイページ",
    "washoku:recipe_submit": "レシピ投稿",
    "washoku:find_by_nutrition": "栄養で選ぶ",
    "washoku:substitute_list": "代わりの食材",
    "washoku:search": "検索",
    "washoku:activity": "みんなの投稿・コメント",
    "washoku:question_list": "Q&A",
    "washoku:column_list": "コラム一覧",
    "washoku:product_list": "おすすめ商品",
    "washoku:link_list": "参考リンク一覧",
    "washoku:poll_list": "アンケート一覧",
    "washoku:notification_list": "お知らせ",
    "washoku:my_favorites": "お気に入り",
}


def _resolve(path):

    try:
        return resolve(path)
    except Resolver404:
        return None


def page_titles(paths):
    """{path: 表示名} を返す。分からないページは入れない。"""

    titles = {}
    wanted = {}

    for path in paths:

        match = _resolve(path)

        if match is None:
            continue

        name = match.view_name

        if name in DETAIL_PAGES:
            model_label, kwarg, field, lookup = DETAIL_PAGES[name]
            value = match.kwargs.get(kwarg)
            if value is not None:
                wanted.setdefault(name, {})[path] = value
        elif name in PAGE_NAMES:
            titles[path] = PAGE_NAMES[name]

    # モデルごとに1回だけ問い合わせる
    for name, path_values in wanted.items():

        model_label, kwarg, field, lookup = DETAIL_PAGES[name]

        try:
            model = apps.get_model(model_label)
            found = dict(
                model.objects
                .filter(**{f"{lookup}__in": set(path_values.values())})
                .values_list(lookup, field)
            )
        except Exception:
            logger.exception("Failed to load page titles for %s", name)
            continue

        for path, value in path_values.items():
            title = found.get(value)
            if title is None and lookup == "pk":
                title = found.get(int(value)) if str(value).isdigit() else None
            if title:
                titles[path] = str(title)

    return titles
