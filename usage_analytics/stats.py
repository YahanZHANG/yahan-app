"""
解析ページの集計。

メモリを食わないように、重い数え上げはDB (GROUP BY) にまかせ、
Python に持ってくるのは「訪問ごと」「訪問者ごと」の小さな行だけにする。
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from datetime import timezone as dt_timezone
from itertools import combinations

from django.db.models import Count, Max, Min, Sum
from django.db.models.functions import TruncDate, TruncWeek
from django.utils import timezone

from .browsers import browser_info

DEVICE_NAMES = {"mobile": "スマホ", "desktop": "パソコン", "tablet": "タブレット", "other": "その他"}
DEVICE_ICONS = {"mobile": "📱", "desktop": "💻", "tablet": "📟", "other": "❔"}


def device_info(key):
    key = key or "other"
    return {"key": key, "name": DEVICE_NAMES.get(key, key), "icon": DEVICE_ICONS.get(key, "❔")}
from .catalog import app_info
from .models import (
    AnalyticsExclusion,
    NewsSummaryRead,
    PageView,
    PublicNewsArticleClick,
    UserNewsArticleClick,
)
from .sources import SOURCE_ORDER, source_info


PERIOD_CHOICES = (7, 30, 90, 365)

DEFAULT_PERIOD = 30

ONLINE_MINUTES = 5

WEEKDAYS = ("月", "火", "水", "木", "金", "土", "日")


# =========================================================
# Scope (期間・アプリ・除外)
# =========================================================

@dataclass
class Scope:

    days: int
    app: str = ""
    end: datetime = field(default_factory=timezone.now)

    def __post_init__(self):

        tz = timezone.get_current_timezone()
        today = timezone.localdate(self.end)

        # 今日を含めて days 日分 (0時区切り)
        self.start = datetime.combine(
            today - timedelta(days=self.days - 1), time.min, tzinfo=tz
        )
        self.previous_start = self.start - timedelta(days=self.days)
        self.bucket = "week" if self.days > 90 else "day"
        self.excluded_user_ids = list(
            AnalyticsExclusion.objects.values_list("user_id", flat=True)
        )

    # -----------------------------------------------------

    def base(self):
        """除外アカウントを外した全期間・全アプリ。"""

        views = PageView.objects.all()

        if self.excluded_user_ids:
            excluded_visitors = (
                PageView.objects
                .filter(user_id__in=self.excluded_user_ids)
                .values("visitor_id")
            )
            views = (
                views
                .exclude(user_id__in=self.excluded_user_ids)
                .exclude(visitor_id__in=excluded_visitors)
            )

        return views

    def app_base(self):

        views = self.base()

        if self.app:
            views = views.filter(app_key=self.app)

        return views

    def current(self):

        return self.app_base().filter(accessed_at__gte=self.start, accessed_at__lte=self.end)

    def previous(self):

        return self.app_base().filter(
            accessed_at__gte=self.previous_start, accessed_at__lt=self.start
        )


def parse_period(value):

    try:
        days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_PERIOD

    return days if days in PERIOD_CHOICES else DEFAULT_PERIOD


def local_day():

    return TruncDate("accessed_at", tzinfo=timezone.get_current_timezone())


def bucket_of(day, bucket):

    if bucket == "week":
        return day - timedelta(days=day.weekday())

    return day


def bucket_labels(scope):

    labels = []
    day = timezone.localdate(scope.start)
    last = timezone.localdate(scope.end)

    while day <= last:
        key = bucket_of(day, scope.bucket)
        if not labels or labels[-1] != key:
            labels.append(key)
        day += timedelta(days=1)

    return labels


def format_bucket(day, bucket):

    if bucket == "week":
        return f"{day.month}/{day.day}週"

    return f"{day.month}/{day.day}({WEEKDAYS[day.weekday()]})"


def change(current, previous):
    """前の期間からの増減 (%)。前が0なら None。"""

    if not previous:
        return None

    return round((current - previous) / previous * 100)


# =========================================================
# Summary numbers
# =========================================================

def summary(views):

    totals = views.aggregate(
        page_views=Count("id"),
        visitors=Count("visitor_id", distinct=True),
        visits=Count("visit_id", distinct=True),
        users=Count("user_id", distinct=True),
    )

    totals["pages_per_visit"] = (
        round(totals["page_views"] / totals["visits"], 1) if totals["visits"] else 0
    )

    return totals


def first_seen_map(scope, visitor_ids):
    """訪問者ごとに、(このアプリで) 初めて来た日。"""

    return {
        row["visitor_id"]: timezone.localtime(row["first"]).date()
        for row in (
            scope.app_base()
            .filter(visitor_id__in=visitor_ids)
            .values("visitor_id")
            .annotate(first=Min("accessed_at"))
        )
    }


# =========================================================
# Dashboard data
# =========================================================

def build_dashboard(scope):
    """解析ページに必要な数字をまとめて作る。"""

    current = scope.current()
    previous = scope.previous()

    now_summary = summary(current)
    before_summary = summary(previous)

    # ---------------------------------------------------
    # 訪問者 x 日 (新規/リピーター, 訪問日数)
    # ---------------------------------------------------

    visitor_days = list(
        current.annotate(day=local_day()).values_list("visitor_id", "day").distinct()
    )

    visitor_ids = {visitor_id for visitor_id, _ in visitor_days}
    first_seen = first_seen_map(scope, visitor_ids)

    start_day = timezone.localdate(scope.start)
    new_visitors = {v for v, first in first_seen.items() if first >= start_day}

    previous_visitor_ids = set(
        previous.values_list("visitor_id", flat=True).distinct()
    )
    previous_first_seen = first_seen_map(scope, previous_visitor_ids)
    previous_start_day = timezone.localdate(scope.previous_start)
    previous_new = sum(
        1 for first in previous_first_seen.values()
        if previous_start_day <= first < start_day
    )

    now_summary["new_visitors"] = len(new_visitors)
    now_summary["returning_visitors"] = len(visitor_ids) - len(new_visitors)
    before_summary["new_visitors"] = previous_new

    labels = bucket_labels(scope)
    new_by_bucket = defaultdict(set)
    returning_by_bucket = defaultdict(set)
    days_per_visitor = Counter()

    for visitor_id, day in visitor_days:
        key = bucket_of(day, scope.bucket)
        days_per_visitor[visitor_id] += 1
        first = first_seen.get(visitor_id)
        if first is not None and bucket_of(first, scope.bucket) == key:
            new_by_bucket[key].add(visitor_id)
        else:
            returning_by_bucket[key].add(visitor_id)

    returning_by_bucket = {
        key: visitors - new_by_bucket[key] for key, visitors in returning_by_bucket.items()
    }

    visitors_chart = {
        "labels": [format_bucket(day, scope.bucket) for day in labels],
        "series": [
            {
                "name": "初めての人",
                "color": "s1",
                "values": [len(new_by_bucket.get(day, ())) for day in labels],
            },
            {
                "name": "また来た人",
                "color": "s3",
                "values": [len(returning_by_bucket.get(day, ())) for day in labels],
            },
        ],
        "unit": "人",
    }

    # ---------------------------------------------------
    # 閲覧数の推移 (アプリ別)
    # ---------------------------------------------------

    app_day_rows = (
        current.annotate(day=local_day())
        .values("day", "app_key")
        .annotate(n=Count("id"))
    )

    app_totals = Counter()
    app_day = defaultdict(Counter)

    for row in app_day_rows:
        key = bucket_of(row["day"], scope.bucket)
        app_totals[row["app_key"]] += row["n"]
        app_day[row["app_key"]][key] += row["n"]

    page_views_chart = {
        "labels": visitors_chart["labels"],
        "series": app_series(app_totals, app_day, labels),
        "unit": "ページ",
    }

    # ---------------------------------------------------
    # 訪問ごとの行
    # ---------------------------------------------------

    visits = visit_rows(scope, current)

    # ---------------------------------------------------
    # 流入元
    # ---------------------------------------------------

    source_day = defaultdict(Counter)
    source_type_totals = Counter()
    source_rows = {}

    for visit in visits:
        key = bucket_of(timezone.localtime(visit["start"]).date(), scope.bucket)
        source_type = visit["source_type"] or "unknown"
        source_day[source_type][key] += 1
        source_type_totals[source_type] += 1

        row_key = (source_type, visit["source_label"] or source_info(source_type)["short"])
        row = source_rows.setdefault(row_key, {
            "type": source_info(source_type),
            "label": row_key[1],
            "visits": 0,
            "visitors": set(),
            "new_visitors": set(),
            "pages": 0,
            "apps": Counter(),
        })
        row["visits"] += 1
        row["visitors"].add(visit["visitor_id"])
        if visit["visitor_id"] in new_visitors and visit["is_first_visit"]:
            row["new_visitors"].add(visit["visitor_id"])
        row["pages"] += visit["pages"]
        row["apps"][visit["entry_app"]] += 1

    sources_chart = {
        "labels": visitors_chart["labels"],
        "series": [
            {
                "name": source_info(source_type)["short"],
                "color": source_info(source_type)["css"],
                "values": [source_day[source_type].get(day, 0) for day in labels],
            }
            for source_type in SOURCE_ORDER
            if source_type_totals[source_type]
        ],
        "unit": "回",
    }

    total_visits = len(visits) or 1

    source_table = sorted(
        (
            {
                "type": row["type"],
                "label": row["label"],
                "visits": row["visits"],
                "share": round(row["visits"] / total_visits * 100),
                "visitors": len(row["visitors"]),
                "new_visitors": len(row["new_visitors"]),
                "pages_per_visit": round(row["pages"] / row["visits"], 1),
                "top_app": app_info(row["apps"].most_common(1)[0][0]),
            }
            for row in source_rows.values()
        ),
        key=lambda row: row["visits"],
        reverse=True,
    )

    source_types = [
        {
            **source_info(source_type),
            "visits": source_type_totals[source_type],
            "share": round(source_type_totals[source_type] / total_visits * 100),
        }
        for source_type in SOURCE_ORDER
        if source_type_totals[source_type]
    ]

    campaigns = campaign_rows(scope, visits)

    # ---------------------------------------------------
    # アプリ別の関心
    # ---------------------------------------------------

    apps = app_interest(scope, current, previous, visits)

    # ---------------------------------------------------
    # いつ来ているか (曜日 x 時間)
    # ---------------------------------------------------

    heatmap = [[0] * 24 for _ in range(7)]

    for visit in visits:
        local = timezone.localtime(visit["start"])
        heatmap[local.weekday()][local.hour] += 1

    heat_max = max((max(row) for row in heatmap), default=0)

    heat_cells = [
        [
            {"hour": hour, "n": n, "level": 0 if not n else min(5, 1 + int(n / heat_max * 4.999))}
            for hour, n in enumerate(row)
        ]
        for row in heatmap
    ]

    # ---------------------------------------------------
    # 何日来ているか / また来た人
    # ---------------------------------------------------

    frequency = frequency_rows(days_per_visitor)

    # 期間の前半に初めて来た人のうち、別の日にもう一度来た人
    halfway = start_day + timedelta(days=max(scope.days // 2, 1))
    early_new = [v for v in new_visitors if first_seen[v] < halfway]
    came_back = [v for v in early_new if days_per_visitor[v] >= 2]

    retention = {
        "base": len(early_new),
        "returned": len(came_back),
        "rate": round(len(came_back) / len(early_new) * 100) if early_new else None,
    }

    # ---------------------------------------------------
    # デバイス
    # ---------------------------------------------------

    device_counter = Counter(visit["device_type"] for visit in visits)
    devices = [
        {
            "name": DEVICE_NAMES.get(key, key),
            "visits": count,
            "share": round(count / total_visits * 100),
        }
        for key, count in device_counter.most_common()
    ]

    # ---------------------------------------------------
    # どこで開いたか (アプリ内ブラウザ)
    # ---------------------------------------------------

    browsers = browser_rows(visits, new_visitors, days_per_visitor)

    return {
        "summary": now_summary,
        "previous": before_summary,
        "changes": {
            key: change(now_summary.get(key, 0), before_summary.get(key, 0))
            for key in ("visitors", "visits", "page_views", "new_visitors", "users")
        },
        "visitors_chart": visitors_chart,
        "page_views_chart": page_views_chart,
        "sources_chart": sources_chart,
        "source_types": source_types,
        "source_table": source_table[:15],
        "campaigns": campaigns,
        "apps": apps,
        "heatmap": {
            "rows": heatmap,
            "cells": list(zip(WEEKDAYS, heat_cells)),
            "max": heat_max,
            "weekdays": WEEKDAYS,
        },
        "frequency": frequency,
        "retention": retention,
        "devices": devices,
        "browsers": browsers,
        "visits_count": len(visits),
        "recent_visits": recent_visits(visits),
    }


def app_series(app_totals, app_day, labels):
    """
    色の付いた主なアプリはそれぞれ1本、それ以外は「その他」にまとめる。
    並びは色の番号順 (隣同士の色が見分けやすい順) に固定。
    """

    main = sorted(
        (app for app in app_totals if app_info(app)["color"]),
        key=lambda app: app_info(app)["color"],
    )
    rest = [app for app in app_totals if not app_info(app)["color"]]

    series = []
    for app in main:
        info = app_info(app)
        series.append({
            "name": f"{info['emoji']} {info['name']}",
            "color": f"s{info['color']}",
            "values": [app_day[app].get(day, 0) for day in labels],
        })

    if rest:
        series.append({
            "name": "その他のアプリ",
            "color": "s0",
            "values": [sum(app_day[app].get(day, 0) for app in rest) for day in labels],
        })

    return series


def visit_rows(scope, current):
    """
    期間内の訪問を1行ずつ。流入元は訪問の最初のページから取る
    (アプリで絞っているときも、その訪問がどこから来たかが分かる)。
    """

    per_visit = {
        row["visit_id"]: row
        for row in (
            current.values("visit_id")
            .annotate(
                pages=Count("id"),
                start=Min("accessed_at"),
                end=Max("accessed_at"),
                visitor_id=Min("visitor_id"),
                user_id=Max("user_id"),
            )
        )
    }

    if not per_visit:
        return []

    visit_ids = current.values("visit_id")

    starts = {
        row["visit_id"]: row
        for row in (
            scope.base()
            .filter(is_visit_start=True, visit_id__in=visit_ids)
            .values(
                "visit_id",
                "source_type",
                "source_label",
                "device_type",
                "browser",
                "app_key",
                "utm_source",
                "utm_medium",
                "utm_campaign",
                "is_new_visitor",
                "path",
            )
        )
    }

    apps_per_visit = defaultdict(set)
    for visit_id, app_key in current.values_list("visit_id", "app_key").distinct():
        apps_per_visit[visit_id].add(app_key)

    first_visit_of = {}

    visits = []
    for visit_id, row in per_visit.items():
        start = starts.get(visit_id, {})
        visit = {
            "visit_id": visit_id,
            "visitor_id": row["visitor_id"],
            "user_id": row["user_id"],
            "pages": row["pages"],
            "start": row["start"],
            "end": row["end"],
            "source_type": start.get("source_type", ""),
            "source_label": start.get("source_label", ""),
            "device_type": start.get("device_type", "other"),
            "device": device_info(start.get("device_type", "other")),
            "browser": browser_info(start.get("browser", "")),
            "entry_app": start.get("app_key") or next(iter(apps_per_visit[visit_id]), "portal"),
            "entry_path": start.get("path", ""),
            "utm_source": start.get("utm_source", ""),
            "utm_medium": start.get("utm_medium", ""),
            "utm_campaign": start.get("utm_campaign", ""),
            "apps": apps_per_visit[visit_id],
        }
        visits.append(visit)

        earliest = first_visit_of.get(row["visitor_id"])
        if earliest is None or visit["start"] < earliest["start"]:
            first_visit_of[row["visitor_id"]] = visit

    for visit in visits:
        visit["is_first_visit"] = first_visit_of[visit["visitor_id"]] is visit

    visits.sort(key=lambda visit: visit["start"], reverse=True)

    return visits


def campaign_rows(scope, visits):

    rows = {}

    for visit in visits:
        if not visit["utm_source"]:
            continue
        key = (visit["utm_source"], visit["utm_medium"], visit["utm_campaign"])
        row = rows.setdefault(key, {
            "source": key[0],
            "medium": key[1],
            "campaign": key[2],
            "visits": 0,
            "visitors": set(),
            "pages": 0,
            "first": visit["start"],
            "last": visit["start"],
        })
        row["visits"] += 1
        row["visitors"].add(visit["visitor_id"])
        row["pages"] += visit["pages"]
        row["first"] = min(row["first"], visit["start"])
        row["last"] = max(row["last"], visit["start"])

    # その後も戻ってきたか (キャンペーンで来た人が別の訪問をしたか)
    visits_per_visitor = Counter(visit["visitor_id"] for visit in visits)

    result = []
    for row in rows.values():
        returned = sum(1 for v in row["visitors"] if visits_per_visitor[v] >= 2)
        result.append({
            **{k: row[k] for k in ("source", "medium", "campaign", "visits", "first", "last")},
            "visitors": len(row["visitors"]),
            "returned": returned,
            "pages_per_visit": round(row["pages"] / row["visits"], 1),
        })

    return sorted(result, key=lambda row: row["visits"], reverse=True)[:10]


def app_interest(scope, current, previous, visits):

    rows = {
        row["app_key"]: row
        for row in current.values("app_key").annotate(
            page_views=Count("id"),
            visitors=Count("visitor_id", distinct=True),
            visits=Count("visit_id", distinct=True),
            users=Count("user_id", distinct=True),
        )
    }

    previous_visitors = dict(
        previous.values("app_key")
        .annotate(n=Count("visitor_id", distinct=True))
        .values_list("app_key", "n")
    )

    total_visitors = len({visit["visitor_id"] for visit in visits}) or 1

    # 1回の訪問で複数のアプリを見た組み合わせ
    pair_counter = Counter()
    multi_app_visits = 0
    for visit in visits:
        if len(visit["apps"]) >= 2:
            multi_app_visits += 1
            for pair in combinations(sorted(visit["apps"]), 2):
                pair_counter[pair] += 1

    # 訪問者ごとに見たアプリ
    visitor_apps = defaultdict(set)
    for visit in visits:
        visitor_apps[visit["visitor_id"]] |= visit["apps"]

    multi_app_visitors = sum(1 for apps in visitor_apps.values() if len(apps) >= 2)

    apps = []
    for app_key, row in rows.items():
        info = app_info(app_key)
        apps.append({
            **info,
            "color_class": f"s{info['color']}" if info["color"] else "s0",
            "page_views": row["page_views"],
            "visitors": row["visitors"],
            "visits": row["visits"],
            "users": row["users"],
            "share": round(row["visitors"] / total_visitors * 100),
            "pages_per_visit": round(row["page_views"] / row["visits"], 1) if row["visits"] else 0,
            "previous_visitors": previous_visitors.get(app_key, 0),
            "change": change(row["visitors"], previous_visitors.get(app_key, 0)),
        })

    apps.sort(key=lambda app: (app["visitors"], app["page_views"]), reverse=True)

    max_visitors = max((app["visitors"] for app in apps), default=0) or 1
    for app in apps:
        app["bar"] = round(app["visitors"] / max_visitors * 100)

    return {
        "rows": apps,
        "pairs": [
            {"a": app_info(a), "b": app_info(b), "visits": n}
            for (a, b), n in pair_counter.most_common(5)
        ],
        "multi_app_visits": multi_app_visits,
        "multi_app_visitors": multi_app_visitors,
        "total_visitors": total_visitors if visits else 0,
    }


def browser_rows(visits, new_visitors, days_per_visitor):
    """
    開いた場所ごとの訪問。アプリ内ブラウザは cookie が残りにくいので、
    「初めての人」「1日だけの人」の割合が高くなりがち (同じ人の数え直し)。
    """

    rows = {}

    for visit in visits:
        info = visit["browser"]
        row = rows.setdefault(info["key"], {**info, "visits": 0, "visitors": set()})
        row["visits"] += 1
        row["visitors"].add(visit["visitor_id"])

    total_visits = len(visits) or 1

    result = []
    for row in rows.values():
        visitors = row.pop("visitors")
        count = len(visitors) or 1
        result.append({
            **row,
            "visitors": len(visitors),
            "share": round(row["visits"] / total_visits * 100),
            "new_share": round(sum(1 for v in visitors if v in new_visitors) / count * 100),
            "one_day_share": round(sum(1 for v in visitors if days_per_visitor[v] == 1) / count * 100),
        })

    # 「記録なし」(以前のデータ) はいちばん下
    result.sort(key=lambda row: (not row["key"], -row["visits"]))

    recorded = [row for row in result if row["key"]]
    in_app_visits = sum(row["visits"] for row in recorded if row["in_app"])
    recorded_visits = sum(row["visits"] for row in recorded)

    max_visits = max((row["visits"] for row in result), default=0) or 1
    for row in result:
        row["bar"] = round(row["visits"] / max_visits * 100)

    return {
        "rows": result,
        "in_app_visits": in_app_visits,
        "recorded_visits": recorded_visits,
        "in_app_share": round(in_app_visits / recorded_visits * 100) if recorded_visits else None,
    }


def frequency_rows(days_per_visitor):

    groups = (
        ("1日だけ", 1, 1),
        ("2日", 2, 2),
        ("3〜4日", 3, 4),
        ("5〜9日", 5, 9),
        ("10日以上", 10, 10_000),
    )

    total = len(days_per_visitor) or 1
    rows = []

    for label, low, high in groups:
        count = sum(1 for days in days_per_visitor.values() if low <= days <= high)
        rows.append({"label": label, "visitors": count, "share": round(count / total * 100)})

    max_count = max((row["visitors"] for row in rows), default=0) or 1
    for row in rows:
        row["bar"] = round(row["visitors"] / max_count * 100)

    return rows


def live_status(scope):
    """
    いまの状況 (マージ・デプロイのタイミング確認用)。
    アプリの絞り込みに関係なく、サイト全体・ログインなしの人も含めて数える。
    """

    now = timezone.now()
    base = scope.base()

    windows = []
    for minutes in (ONLINE_MINUTES, 15, 30):
        recent = base.filter(accessed_at__gte=now - timedelta(minutes=minutes))
        windows.append({
            "minutes": minutes,
            "visitors": recent.values("visitor_id").distinct().count(),
        })

    recent = base.filter(accessed_at__gte=now - timedelta(minutes=ONLINE_MINUTES))

    by_app = (
        recent.values("app_key")
        .annotate(n=Count("visitor_id", distinct=True))
        .order_by("-n")
    )

    user_ids = set(
        recent.exclude(user=None).values_list("user_id", flat=True).distinct()
    )

    last = base.order_by("-accessed_at").values_list("accessed_at", flat=True).first()

    return {
        "visitors": windows[0]["visitors"],
        "minutes": ONLINE_MINUTES,
        "windows": windows,
        "apps": [{**app_info(row["app_key"]), "visitors": row["n"]} for row in by_app],
        "user_ids": user_ids,
        "signed_in": len(user_ids),
        "anonymous": (
            recent.exclude(
                visitor_id__in=recent.exclude(user=None).values("visitor_id")
            )
            .values("visitor_id").distinct().count()
        ),
        "last_seen": last,
        "last_minutes": round((now - last).total_seconds() / 60) if last else None,
        "checked_at": now,
    }


def recent_visits(visits, limit=30):

    return [
        {
            **visit,
            "source": source_info(visit["source_type"] or "unknown"),
            "app_list": [app_info(app) for app in sorted(visit["apps"])],
            "minutes": round((visit["end"] - visit["start"]).total_seconds() / 60),
        }
        for visit in visits[:limit]
    ]


# =========================================================
# Popular pages and articles
# =========================================================

def top_pages(current, limit=15):

    from .titles import page_titles

    rows = list(
        current.values("app_key", "path")
        .annotate(page_views=Count("id"), visitors=Count("visitor_id", distinct=True))
        .order_by("-page_views")[:limit]
    )

    titles = page_titles(row["path"] for row in rows)

    for row in rows:
        row["app"] = app_info(row["app_key"])
        row["title"] = titles.get(row["path"], "")

    return rows


def top_news_clicks(scope, limit=10):

    public = PublicNewsArticleClick.objects.filter(
        clicked_at__gte=scope.start, clicked_at__lte=scope.end
    )
    signed_in = UserNewsArticleClick.objects.filter(
        clicked_at__gte=scope.start, clicked_at__lte=scope.end
    )

    if scope.excluded_user_ids:
        signed_in = signed_in.exclude(user_id__in=scope.excluded_user_ids)
        excluded_visitors = (
            PageView.objects
            .filter(user_id__in=scope.excluded_user_ids)
            .values("visitor_id")
        )
        public = public.exclude(visitor_id__in=excluded_visitors)

    counter = Counter()
    info = {}

    for clicks in (public, signed_in):
        for row in (
            clicks.values("article_id", "article_title", "source_name")
            .annotate(n=Count("id"))
        ):
            counter[row["article_id"]] += row["n"]
            info[row["article_id"]] = row

    return [
        {
            "article_id": article_id,
            "title": info[article_id]["article_title"],
            "source": info[article_id]["source_name"],
            "clicks": clicks,
        }
        for article_id, clicks in counter.most_common(limit)
    ]


# 元記事クリックは、要約を読んだうえで「もっと知りたい」と思った強い反応なので重めにする
CLICK_WEIGHT = 3

# ニュースは新しさが大事なので、解析画面の期間に関係なく直近3日間 (今日を含む) で数える
NEWS_RANKING_DAYS = 3


def top_news_reads(limit=15):
    """
    要約の閲覧 (推定) と元記事クリックを合わせた、よく読まれた記事の順位。
    点数 = 要約の閲覧 (重みの合計) + 元記事クリック × CLICK_WEIGHT
    """

    scope = Scope(days=NEWS_RANKING_DAYS)

    reads = NewsSummaryRead.objects.filter(
        read_at__gte=scope.start, read_at__lte=scope.end
    )

    if scope.excluded_user_ids:
        excluded_visitors = (
            PageView.objects
            .filter(user_id__in=scope.excluded_user_ids)
            .values("visitor_id")
        )
        reads = (
            reads
            .exclude(user_id__in=scope.excluded_user_ids)
            .exclude(visitor_id__in=excluded_visitors)
        )

    rows = {}

    for row in (
        reads.values("article_id", "article_title", "source_name")
        .annotate(total=Sum("weight"), people=Count("visitor_id", distinct=True))
    ):
        rows[row["article_id"]] = {
            "title": row["article_title"],
            "source": row["source_name"],
            "reads": row["total"] or 0,
            "people": row["people"],
            "clicks": 0,
        }

    for click in top_news_clicks(scope, limit=None):
        row = rows.setdefault(click["article_id"], {
            "title": click["title"],
            "source": click["source"],
            "reads": 0,
            "people": 0,
            "clicks": 0,
        })
        row["clicks"] = click["clicks"]

    for row in rows.values():
        row["reads"] = round(row["reads"], 1)
        row["score"] = round(row["reads"] + row["clicks"] * CLICK_WEIGHT, 1)

    ranked = sorted(rows.values(), key=lambda row: row["score"], reverse=True)

    return ranked[:limit]


# =========================================================
# Signed-in users
# =========================================================

def signed_in_users(current, limit=30):

    rows = list(
        current.filter(user__isnull=False)
        .values("user_id", "user__username")
        .annotate(
            page_views=Count("id"),
            visits=Count("visit_id", distinct=True),
            active_days=Count(local_day(), distinct=True),
            last_seen=Max("accessed_at"),
        )
        .order_by("-active_days", "-page_views")[:limit]
    )

    apps = defaultdict(Counter)
    for user_id, app_key, n in (
        current.filter(user_id__in=[row["user_id"] for row in rows])
        .values_list("user_id", "app_key")
        .annotate(n=Count("id"))
    ):
        apps[user_id][app_key] = n

    for row in rows:
        row["apps"] = [app_info(app) for app, _ in apps[row["user_id"]].most_common(4)]

    return rows


# =========================================================
# Person timeline (訪問者 / ユーザー)
# =========================================================

def person_timeline(views, limit=400):
    """
    1人分の閲覧を、訪問ごとにまとめる。新しい訪問から。
    """

    from .titles import page_titles

    rows = list(
        views.order_by("-accessed_at").values(
            "visit_id",
            "visitor_id",
            "app_key",
            "path",
            "accessed_at",
            "is_visit_start",
            "source_type",
            "source_label",
            "device_type",
            "browser",
            "utm_campaign",
        )[:limit]
    )

    titles = page_titles({row["path"] for row in rows})

    visits = {}
    for row in reversed(rows):
        visit = visits.setdefault(row["visit_id"], {
            "visit_id": row["visit_id"],
            "start": row["accessed_at"],
            "end": row["accessed_at"],
            "pages": [],
            "source": source_info("unknown"),
            "source_label": "",
            "device_type": row["device_type"],
            "device": device_info(row["device_type"]),
            "browser": browser_info(row["browser"]),
            "apps": [],
        })
        visit["end"] = row["accessed_at"]
        if row["is_visit_start"]:
            visit["source"] = source_info(row["source_type"] or "unknown")
            visit["source_label"] = row["source_label"]
            visit["device_type"] = row["device_type"]
            visit["device"] = device_info(row["device_type"])
            visit["browser"] = browser_info(row["browser"])
        info = app_info(row["app_key"])
        if info not in visit["apps"]:
            visit["apps"].append(info)
        visit["pages"].append({
            "at": row["accessed_at"],
            "app": info,
            "path": row["path"],
            "title": titles.get(row["path"], ""),
        })

    result = sorted(visits.values(), key=lambda visit: visit["start"], reverse=True)

    for visit in result:
        visit["weekday"] = WEEKDAYS[timezone.localtime(visit["start"]).weekday()]
        visit["minutes"] = round((visit["end"] - visit["start"]).total_seconds() / 60)

    return result


def person_summary(views):

    totals = views.aggregate(
        page_views=Count("id"),
        visits=Count("visit_id", distinct=True),
        first=Min("accessed_at"),
        last=Max("accessed_at"),
        active_days=Count(local_day(), distinct=True),
    )

    totals["apps"] = [
        {**app_info(row["app_key"]), "page_views": row["n"]}
        for row in views.values("app_key").annotate(n=Count("id")).order_by("-n")
    ]

    max_views = max((app["page_views"] for app in totals["apps"]), default=0) or 1
    for app in totals["apps"]:
        app["bar"] = round(app["page_views"] / max_views * 100)

    totals["sources"] = [
        {**source_info(row["source_type"]), "label": row["source_label"], "visits": row["n"]}
        for row in (
            views.filter(is_visit_start=True)
            .values("source_type", "source_label")
            .annotate(n=Count("id"))
            .order_by("-n")[:5]
        )
    ]

    return totals


def activity_strip(views, days=56):
    """最近8週間、日ごとの閲覧数 (足あとカレンダー用)。"""

    today = timezone.localdate()
    start_day = today - timedelta(days=days - 1)
    tz = timezone.get_current_timezone()

    counts = dict(
        views.filter(accessed_at__gte=datetime.combine(start_day, time.min, tzinfo=tz))
        .annotate(day=local_day())
        .values("day")
        .annotate(n=Count("id"))
        .values_list("day", "n")
    )

    peak = max(counts.values(), default=0) or 1

    cells = []
    for offset in range(days):
        day = start_day + timedelta(days=offset)
        n = counts.get(day, 0)
        level = 0 if n == 0 else min(4, 1 + int(n / peak * 3.999))
        cells.append({"day": day, "n": n, "level": level})

    return cells



# =========================================================
# 訪問者と訪問回数の推移 / 過去24時間
# =========================================================

def traffic_chart(scope):
    """期間内の日ごと (長い期間は週ごと) の、来た人と訪問回数 (折れ線)。"""

    tz = timezone.get_current_timezone()
    trunc = TruncWeek("accessed_at", tzinfo=tz) if scope.bucket == "week" else local_day()

    rows = (
        scope.current()
        .annotate(bucket=trunc)
        .values("bucket")
        .annotate(
            visitors=Count("visitor_id", distinct=True),
            visits=Count("visit_id", distinct=True),
        )
    )

    by_bucket = {}
    for row in rows:
        key = row["bucket"]
        if isinstance(key, datetime):
            key = timezone.localtime(key, tz).date() if timezone.is_aware(key) else key.date()
        by_bucket[key] = row

    labels = bucket_labels(scope)

    return {
        "labels": [format_bucket(day, scope.bucket) for day in labels],
        "series": [
            {"name": "来た人", "color": "s1", "values": [by_bucket.get(day, {}).get("visitors", 0) for day in labels]},
            {"name": "訪問回数", "color": "s3", "values": [by_bucket.get(day, {}).get("visits", 0) for day in labels]},
        ],
        "unit": "",
        "mode": "line",
    }


DAY_SLOT_MINUTES = 15


def last_day_chart(scope):
    """過去24時間の、15分ごとの来た人と訪問回数 (折れ線。目盛りは1時間ごと)。"""

    # 時刻の計算は UTC で (現地時間のまま引き算すると、夏時間の切り替え日に1時間ずれる)
    end = scope.end.astimezone(dt_timezone.utc)
    end = end.replace(minute=end.minute - end.minute % DAY_SLOT_MINUTES, second=0, microsecond=0)
    slots = 24 * 60 // DAY_SLOT_MINUTES
    start = end - timedelta(minutes=DAY_SLOT_MINUTES * (slots - 1))

    visitors = defaultdict(set)
    visits = defaultdict(set)

    rows = (
        scope.app_base()
        .filter(accessed_at__gte=start, accessed_at__lte=scope.end)
        .values_list("visitor_id", "visit_id", "accessed_at")
    )

    for visitor_id, visit_id, accessed_at in rows.iterator(chunk_size=2000):
        index = int((accessed_at - start).total_seconds() // (DAY_SLOT_MINUTES * 60))
        if 0 <= index < slots:
            visitors[index].add(visitor_id)
            visits[index].add(visit_id)

    labels = [
        timezone.localtime(start + timedelta(minutes=DAY_SLOT_MINUTES * i)).strftime("%H:%M")
        for i in range(slots)
    ]

    # 目盛りは「ちょうどの時刻」から1時間ごと
    first_hour = next((i for i, label in enumerate(labels) if label.endswith(":00")), 0)

    return {
        "labels": labels,
        "series": [
            {"name": "来た人", "color": "s1", "values": [len(visitors[i]) for i in range(slots)]},
            {"name": "訪問回数", "color": "s3", "values": [len(visits[i]) for i in range(slots)]},
        ],
        "unit": "",
        "mode": "line",
        "tickStep": 60 // DAY_SLOT_MINUTES,
        "tickOffset": first_hour,
    }
