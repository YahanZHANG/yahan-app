"""
「最近の傾向」の文章を、集計した数字からルールで作る (無料・すぐ出る)。
"""

from collections import Counter

from django.utils.html import format_html

from .catalog import OTHER_APP


def _trend(percent):

    if percent is None or -5 < percent < 5:
        return ""

    return format_html("（前の期間より{}{}%）", "+" if percent > 0 else "−", abs(percent))


def build_insights(scope, data, pages, clicks):
    """要点だけを短く。1行ずつ、数字が中心。"""

    lines = []
    summary = data["summary"]
    changes = data["changes"]

    if not summary["visitors"]:
        return [{"icon": "💤", "text": "この期間の記録はまだありません。"}]

    # 人数
    lines.append({
        "icon": "👥",
        "text": format_html(
            "来た人 <strong>{}人</strong>{}・閲覧 {}回{}",
            summary["visitors"],
            _trend(changes["visitors"]),
            summary["page_views"],
            "（少人数なので参考程度）" if summary["visitors"] < 10 else "",
        ),
    })

    if summary["visitors"] >= 2:
        repeat_share = round(summary["returning_visitors"] / summary["visitors"] * 100)
        lines.append({
            "icon": "🔁",
            "text": format_html("リピーター <strong>{}%</strong>", repeat_share),
        })

    # アプリ (「その他」は除いて見る)
    apps = [app for app in data["apps"]["rows"] if app["key"] != OTHER_APP]

    if apps and not scope.app:
        top = apps[0]
        parts = [format_html("いちばん人気は {} {}（{}人）", top["emoji"], top["name"], top["visitors"])]

        growing = [
            app for app in apps
            if app["change"] is not None and app["visitors"] >= 3 and app["change"] >= 20
        ]
        if growing:
            best = max(growing, key=lambda app: app["change"])
            parts.append(format_html("{} が +{}%", best["name"], best["change"]))

        falling = [
            app for app in apps
            if app["change"] is not None and app["previous_visitors"] >= 5 and app["change"] <= -30
        ]
        if falling:
            worst = min(falling, key=lambda app: app["change"])
            parts.append(format_html("{} が −{}%", worst["name"], -worst["change"]))

        lines.append({"icon": "🏆", "text": format_html_join_jp(parts)})

    # 経路
    source_types = sorted(data["source_types"], key=lambda row: row["visits"], reverse=True)
    if source_types:
        top = source_types[0]
        outside = [
            row for row in data["source_table"]
            if row["type"]["key"] not in ("direct", "unknown")
        ]
        lines.append({
            "icon": "🧭",
            "text": format_html(
                "経路は「{}」が {}%{}",
                top["short"],
                top["share"],
                format_html("、外からは {} が最多（{}回）", outside[0]["label"], outside[0]["visits"]) if outside else "",
            ),
        })

    # 時間帯
    heat = data["heatmap"]["rows"]
    if data["visits_count"] >= 5:
        weekday_totals = Counter({i: sum(row) for i, row in enumerate(heat)})
        hour_totals = Counter({h: sum(row[h] for row in heat) for h in range(24)})
        lines.append({
            "icon": "🕒",
            "text": format_html(
                "多いのは {}曜日・{}時台",
                data["heatmap"]["weekdays"][weekday_totals.most_common(1)[0][0]],
                hour_totals.most_common(1)[0][0],
            ),
        })

    return lines


def format_html_join_jp(parts):

    text = parts[0]
    for part in parts[1:]:
        text = format_html("{}、{}", text, part)
    return text
