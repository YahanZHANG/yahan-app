"""
「使い方の傾向」: よく使う人が見ているページ、すぐ帰った人が最後に見たページ、
最近見られ始めたページを集計し、改善のヒントをルールで作る (無料・AIなし)。

重くならないように、見るのは最大 BEHAVIOR_DAYS 日分だけ。
"""

from collections import Counter, defaultdict
from datetime import timedelta

from django.utils import timezone
from django.utils.html import format_html

from .catalog import app_info
from .titles import page_titles


BEHAVIOR_DAYS = 30

# この日数以上来た人を「よく使う人」とする
REGULAR_DAYS = 3

# 1回だけ来て、このページ数以下で帰った人を「すぐ帰った人」とする
SHORT_VISIT_PAGES = 2

TOP = 6


def _page_rows(counter, visitors, titles, total, limit=TOP):

    rows = []

    for (app_key, path), count in counter.most_common(limit):
        rows.append({
            "app": app_info(app_key),
            "path": path,
            "title": titles.get(path, ""),
            "count": count,
            "visitors": len(visitors[app_key, path]),
            "share": round(count / total * 100) if total else 0,
        })

    return rows


def _name(row):
    return row["title"] or row["path"]


def build_behavior(scope):

    start = max(scope.start, scope.end - timedelta(days=BEHAVIOR_DAYS))
    views = scope.app_base().filter(accessed_at__gte=start, accessed_at__lte=scope.end)

    rows = views.order_by("accessed_at").values_list(
        "visitor_id", "visit_id", "app_key", "path", "accessed_at"
    )

    days_of = defaultdict(set)
    visits_of = defaultdict(set)
    visit_pages = defaultdict(list)

    for visitor_id, visit_id, app_key, path, accessed_at in rows.iterator(chunk_size=2000):
        days_of[visitor_id].add(timezone.localtime(accessed_at).date())
        visits_of[visitor_id].add(visit_id)
        visit_pages[visit_id].append((visitor_id, app_key, path, accessed_at))

    if not visit_pages:
        return None

    regulars = {v for v, days in days_of.items() if len(days) >= REGULAR_DAYS}

    # よく使う人が見ているページ / ほかの人が見ているページ
    regular_pages = Counter()
    regular_visitors = defaultdict(set)
    other_pages = Counter()

    # 1回だけ来てすぐ帰った人が、最後に見たページ
    exit_pages = Counter()
    exit_visitors = defaultdict(set)
    short_visitors = set()

    # 最近の関心: 後半と前半でページの閲覧を比べる
    half = start + (scope.end - start) / 2
    recent = Counter()
    earlier = Counter()
    recent_visitors = defaultdict(set)

    for visit_id, pages in visit_pages.items():

        visitor_id = pages[0][0]

        for _, app_key, path, accessed_at in pages:
            key = (app_key, path)
            if visitor_id in regulars:
                regular_pages[key] += 1
                regular_visitors[key].add(visitor_id)
            else:
                other_pages[key] += 1
            if accessed_at >= half:
                recent[key] += 1
                recent_visitors[key].add(visitor_id)
            else:
                earlier[key] += 1

        if len(visits_of[visitor_id]) == 1 and len(pages) <= SHORT_VISIT_PAGES:
            _, app_key, path, _ = pages[-1]
            exit_pages[app_key, path] += 1
            exit_visitors[app_key, path].add(visitor_id)
            short_visitors.add(visitor_id)

    rising = Counter()
    for key, count in recent.items():
        if count >= 3 and len(recent_visitors[key]) >= 2:
            rising[key] = count - earlier.get(key, 0)
    rising = Counter({key: gain for key, gain in rising.items() if gain > 0})

    paths = {path for _, path in list(regular_pages) + list(exit_pages) + list(rising) + list(other_pages)}
    titles = page_titles(paths)

    regular_rows = _page_rows(regular_pages, regular_visitors, titles, sum(regular_pages.values()))
    exit_rows = _page_rows(exit_pages, exit_visitors, titles, len(short_visitors))

    rising_rows = []
    for (app_key, path), gain in rising.most_common(TOP):
        before = earlier.get((app_key, path), 0)
        rising_rows.append({
            "app": app_info(app_key),
            "path": path,
            "title": titles.get(path, ""),
            "count": recent[app_key, path],
            "before": before,
            "visitors": len(recent_visitors[app_key, path]),
        })

    total_visitors = len(days_of)
    one_visit = sum(1 for visits in visits_of.values() if len(visits) == 1)

    return {
        "days": max(1, round((scope.end - start).total_seconds() / 86400)),
        "regular_days": REGULAR_DAYS,
        "short_pages": SHORT_VISIT_PAGES,
        "visitors": total_visitors,
        "regulars": len(regulars),
        "short_visitors": len(short_visitors),
        "one_visit": one_visit,
        "regular_pages": regular_rows,
        "exit_pages": exit_rows,
        "rising_pages": rising_rows,
        "advice": build_advice(
            total_visitors, regulars, short_visitors, one_visit,
            regular_rows, exit_rows, rising_rows, other_pages,
        ),
    }


def build_advice(total, regulars, short_visitors, one_visit, regular_rows, exit_rows, rising_rows, other_pages):
    """数字から、次に手を入れるとよさそうなところを短い文で出す。"""

    advice = []

    if not total:
        return advice

    short_share = round(len(short_visitors) / total * 100)

    if exit_rows and short_share >= 30:
        top = exit_rows[0]
        advice.append({
            "icon": "🚪",
            "text": format_html(
                "1回だけ来てすぐ帰った人が <strong>{}%</strong> います。いちばん多く最後に見ていたのは"
                "「{}」です。このページから次に見るもの（関連レシピ・食材・HOMEへの道）を目立たせると、続けて見てもらえそうです。",
                short_share, _name(top),
            ),
        })

    # よく使う人は見ているが、ほかの人はあまり見ていないページ
    other_total = sum(other_pages.values()) or 1
    regular_total = sum(row["count"] for row in regular_rows) or 1

    for row in regular_rows:
        key = (row["app"]["key"], row["path"]) if "key" in row["app"] else None
        other_share = other_pages.get(key, 0) / other_total if key else 0
        regular_share = row["count"] / regular_total
        if regular_share >= 0.1 and other_share < regular_share / 2:
            advice.append({
                "icon": "💡",
                "text": format_html(
                    "よく使う人は「{}」をよく見ていますが、ほかの人はあまり見ていません。"
                    "HOMEや初めての人向けの案内で見せると、使い続けてもらうきっかけになりそうです。",
                    _name(row),
                ),
            })
            break

    if rising_rows:
        top = rising_rows[0]
        advice.append({
            "icon": "📈",
            "text": format_html(
                "最近「{}」がよく見られています（{}回、前半は{}回）。関連するコラムやアンケートを足すと、さらに盛り上がりそうです。",
                _name(top), top["count"], top["before"],
            ),
        })

    if total >= 5 and len(regulars) / total < 0.15:
        advice.append({
            "icon": "🔔",
            "text": format_html(
                "3日以上来ている人はまだ <strong>{}人</strong>（{}%）です。"
                "お知らせの通知やホーム画面への追加の案内で、また来てもらう仕掛けを増やすとよさそうです。",
                len(regulars), round(len(regulars) / total * 100),
            ),
        })

    if not advice:
        advice.append({"icon": "👍", "text": "大きく気になるところはありません。この調子で投稿や話題を増やしていきましょう。"})

    return advice
