"""
「最近の傾向」の文章を、集計した数字からルールで作る (無料・すぐ出る)。
"""

from collections import Counter

from django.utils.html import format_html

from .models import PageView


def _trend(percent):

    if percent is None:
        return ""

    if percent >= 5:
        return format_html("前の期間より <strong>{}%増</strong>", percent)

    if percent <= -5:
        return format_html("前の期間より <strong>{}%減</strong>", -percent)

    return "前の期間とほぼ同じ"


def build_insights(scope, data, pages, clicks):

    lines = []
    summary = data["summary"]
    changes = data["changes"]
    period = f"この{scope.days}日間"

    if not summary["visitors"]:
        return [{"icon": "💤", "text": f"{period}の記録はまだありません。"}]

    # ---------------------------------------------------
    # 人数
    # ---------------------------------------------------

    trend = _trend(changes["visitors"])
    lines.append({
        "icon": "👥",
        "text": format_html(
            "{}に来た人は <strong>{}人</strong>、ページは合計 {} 回見られました{}。",
            period,
            summary["visitors"],
            summary["page_views"],
            format_html("（人数は{}）", trend) if trend else "",
        ),
    })

    if summary["visitors"] >= 2:
        repeat_share = round(summary["returning_visitors"] / summary["visitors"] * 100)
        lines.append({
            "icon": "🔁",
            "text": format_html(
                "初めての人が {}人、前にも来たことがある人が {}人で、"
                "<strong>リピーターが{}%</strong>です。",
                summary["new_visitors"],
                summary["returning_visitors"],
                repeat_share,
            ),
        })

    retention = data["retention"]
    if retention["rate"] is not None and retention["base"] >= 3:
        lines.append({
            "icon": "🌱",
            "text": format_html(
                "期間の前半に初めて来た {}人のうち <strong>{}%</strong> が、別の日にもう一度来ています。",
                retention["base"],
                retention["rate"],
            ),
        })

    # ---------------------------------------------------
    # アプリ
    # ---------------------------------------------------

    apps = data["apps"]["rows"]

    if apps and not scope.app:
        top = apps[0]
        lines.append({
            "icon": top["emoji"],
            "text": format_html(
                "いちばん人が集まっているのは <strong>{}</strong>（{}人・来た人の{}%）。",
                top["name"],
                top["visitors"],
                top["share"],
            ),
        })

        growing = [
            app for app in apps
            if app["change"] is not None and app["visitors"] >= 3 and app["change"] >= 20
        ]
        new_apps = [
            app for app in apps
            if app["previous_visitors"] == 0 and app["visitors"] >= 3
        ]

        if growing:
            best = max(growing, key=lambda app: app["change"])
            lines.append({
                "icon": "📈",
                "text": format_html(
                    "{} {} は前の期間より <strong>{}%</strong> 人が増えていて、伸びています。",
                    best["emoji"], best["name"], best["change"],
                ),
            })

        for app in new_apps[:2]:
            lines.append({
                "icon": "✨",
                "text": format_html(
                    "{} {} にこの期間から人が来はじめました（{}人）。",
                    app["emoji"], app["name"], app["visitors"],
                ),
            })

        falling = [
            app for app in apps
            if app["change"] is not None and app["previous_visitors"] >= 5 and app["change"] <= -30
        ]
        if falling:
            worst = min(falling, key=lambda app: app["change"])
            lines.append({
                "icon": "📉",
                "text": format_html(
                    "{} {} は前の期間より {}% 人が減っています。",
                    worst["emoji"], worst["name"], -worst["change"],
                ),
            })

    if data["apps"]["multi_app_visitors"] and data["apps"]["pairs"]:
        pair = data["apps"]["pairs"][0]
        lines.append({
            "icon": "🔗",
            "text": format_html(
                "複数のアプリを見た人は {}人。よくある組み合わせは {} {} と {} {} です。",
                data["apps"]["multi_app_visitors"],
                pair["a"]["emoji"], pair["a"]["name"],
                pair["b"]["emoji"], pair["b"]["name"],
            ),
        })

    # ---------------------------------------------------
    # 流入元
    # ---------------------------------------------------

    source_types = sorted(data["source_types"], key=lambda row: row["visits"], reverse=True)
    if source_types:
        top = source_types[0]
        lines.append({
            "icon": "🧭",
            "text": format_html(
                "来る経路は「<strong>{}</strong>」がいちばん多く、訪問の{}%です。",
                top["short"], top["share"],
            ),
        })

    outside = [
        row for row in data["source_table"]
        if row["type"]["key"] not in ("direct", "unknown")
    ]
    if outside:
        best = outside[0]
        lines.append({
            "icon": "🚪",
            "text": format_html(
                "外から来た中では <strong>{}</strong>（{}）が {}回でトップ。そこから来た人は1回に平均 {} ページ見ています。",
                best["label"], best["type"]["short"], best["visits"], best["pages_per_visit"],
            ),
        })

        previous_labels = set(
            scope.base()
            .filter(
                is_visit_start=True,
                accessed_at__gte=scope.previous_start,
                accessed_at__lt=scope.start,
            )
            .values_list("source_label", flat=True)
            .distinct()
        )
        has_previous = PageView.objects.filter(accessed_at__lt=scope.start).exists()
        fresh = [row for row in outside if row["label"] not in previous_labels]
        if has_previous and fresh:
            lines.append({
                "icon": "🆕",
                "text": format_html(
                    "新しい流入元: {}（前の期間にはなかった経路です）。",
                    "、".join(f"{row['label']} {row['visits']}回" for row in fresh[:3]),
                ),
            })

    # ---------------------------------------------------
    # いつ・どこで
    # ---------------------------------------------------

    heat = data["heatmap"]["rows"]
    if data["visits_count"] >= 5:
        weekday_totals = Counter({i: sum(row) for i, row in enumerate(heat)})
        hour_totals = Counter({h: sum(row[h] for row in heat) for h in range(24)})
        best_day = weekday_totals.most_common(1)[0][0]
        best_hour = hour_totals.most_common(1)[0][0]
        lines.append({
            "icon": "🕒",
            "text": format_html(
                "よく見られているのは <strong>{}曜日</strong>、時間帯では <strong>{}時台</strong>（スイス時間）です。",
                data["heatmap"]["weekdays"][best_day],
                best_hour,
            ),
        })

    if data["devices"]:
        mobile = next((row for row in data["devices"] if row["name"] == "スマホ"), None)
        if mobile and mobile["share"] >= 50:
            lines.append({
                "icon": "📱",
                "text": format_html("訪問の <strong>{}%</strong> はスマホからです。", mobile["share"]),
            })

    # ---------------------------------------------------
    # 人気
    # ---------------------------------------------------

    titled = [page for page in pages if page["title"]]
    if titled:
        page = titled[0]
        lines.append({
            "icon": "⭐",
            "text": format_html(
                "よく見られているページは「{}」（{} {}・{}回）。",
                page["title"], page["app"]["emoji"], page["app"]["name"], page["page_views"],
            ),
        })

    if clicks:
        lines.append({
            "icon": "📰",
            "text": format_html(
                "Swiss News でいちばん読まれた記事は「{}」（{}回クリック）。",
                clicks[0]["title"], clicks[0]["clicks"],
            ),
        })

    if summary["visitors"] < 10:
        lines.append({
            "icon": "ℹ️",
            "text": "まだ人数が少ないので、傾向は参考程度に見てください。",
        })

    return lines
