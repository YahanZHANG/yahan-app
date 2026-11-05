"""
管理画面「事前アンケートの動き」: 参加・0問目・回答・スキップ・知りたい・質問の追加を、
時刻順に1つの一覧で見る。人 (ブラウザの目印) ごと・参加ごと・日ごとに絞り込める。

URL: /admin/pre_survey/participant/activity/
"""

import uuid
from datetime import datetime, time, timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone

from .models import Answer, FeatureWish, Interest, Participant, Question, Skip


# 1ページに出す最大の件数 (日を選べば、その日の分だけになる)
MAX_EVENTS = 500


def short(text, length=80):
    text = " ".join((text or "").split())
    return text if len(text) <= length else text[:length] + "…"


def person_label(participant, token):
    """だれか: ニックネーム + ブラウザの目印の先頭 (同じ人の行を見分けるため)"""

    name = participant.display_name if participant else "（参加の記録なし）"
    mark = str(token)[:6] if token else "------"
    return name, mark


def parse_day(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def parse_token(value):
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError, AttributeError):
        return None


def collect_events(day=None, token=None, participant_id=None):

    def narrow(queryset, time_field="created_at"):
        if day:
            start = timezone.make_aware(datetime.combine(day, time.min))
            queryset = queryset.filter(**{f"{time_field}__gte": start, f"{time_field}__lt": start + timedelta(days=1)})
        if token:
            queryset = queryset.filter(browser_token=token)
        if participant_id:
            queryset = queryset.filter(**({"pk": participant_id} if queryset.model is Participant else {"participant_id": participant_id}))
        return queryset.order_by(f"-{time_field}")[:MAX_EVENTS]

    events = []

    def add(at, participant, token_value, kind, kind_class, detail, user=None):
        name, mark = person_label(participant, token_value)
        events.append({
            "at": at,
            "participant": participant,
            "token": token_value,
            "name": name,
            "mark": mark,
            "user": user,
            "kind": kind,
            "kind_class": kind_class,
            "detail": detail,
        })

    for p in narrow(Participant.objects.select_related("user")):
        themes = "・".join(p.theme_labels()) or "（テーマ未選択）"
        region = p.get_region_display() if p.region else "地域なし"
        add(p.created_at, p, p.browser_token, "参加の開始", "start",
            f"{p.get_nickname_mode_display() or 'ニックネーム未設定'} / {themes} / {region}", p.user)

    finished = Participant.objects.select_related("user").exclude(finished_at=None)
    for p in narrow(finished, "finished_at"):
        add(p.finished_at, p, p.browser_token, "終了画面", "done", "", p.user)

    for w in narrow(FeatureWish.objects.select_related("participant", "user")):
        detail = "・".join(w.feature_labels())
        if w.other_text:
            detail += f"（その他: {w.other_text}）"
        if w.comment:
            detail += f" ／ ご意見: {short(w.comment, 60)}"
        add(w.created_at, w.participant, w.browser_token, f"0問目: {w.get_response_display()}", "wish", detail, w.user)

    for a in narrow(Answer.objects.select_related("participant", "user", "question")):
        add(a.created_at, a.participant, a.browser_token, "回答", "answer",
            f"Q: {short(a.question.body, 50)} → {short(a.body)}", a.user)

    for s in narrow(Skip.objects.select_related("participant", "user", "question")):
        add(s.created_at, s.participant, s.browser_token, "スキップ", "skip", f"Q: {short(s.question.body, 60)}", s.user)

    for i in narrow(Interest.objects.select_related("participant", "user", "question")):
        add(i.created_at, i.participant, i.browser_token, "私も知りたい", "interest", f"Q: {short(i.question.body, 60)}", i.user)

    member_questions = Question.objects.filter(source=Question.Source.MEMBER).select_related("participant", "user")
    for q in narrow(member_questions):
        add(q.created_at, q.participant, q.browser_token, "質問の追加", "ask",
            f"[{q.get_theme_display()}] {short(q.body)}（{q.get_status_display()}）", q.user)

    events.sort(key=lambda event: event["at"], reverse=True)
    return events[:MAX_EVENTS]


@staff_member_required
def activity_view(request, admin_site=None):

    day_value = request.GET.get("date", "")
    day = parse_day(day_value)
    token = parse_token(request.GET.get("token"))
    participant_id = request.GET.get("participant", "")
    participant_id = int(participant_id) if participant_id.isdigit() else None

    # 何も指定がなければ、今日の分を出す
    if not day_value and not token and not participant_id:
        day = timezone.localdate()

    events = collect_events(day=day, token=token, participant_id=participant_id)

    # 同じ人 (ブラウザの目印) の行に同じ色の印をつける
    palette = 8
    colors = {}
    for event in events:
        if event["token"] and event["token"] not in colors:
            colors[event["token"]] = len(colors) % palette
        event["color"] = colors.get(event["token"], "none")

    context = {
        **(admin_site.each_context(request) if admin_site else {}),
        "title": "事前アンケートの動き",
        "events": events,
        "day": day,
        "token": token,
        "participant_id": participant_id,
        "previous_day": (day - timedelta(days=1)) if day else None,
        "next_day": (day + timedelta(days=1)) if day and day < timezone.localdate() else None,
        "today": timezone.localdate(),
        "max_events": MAX_EVENTS,
        "people": len(colors),
    }
    return render(request, "admin/pre_survey/activity.html", context)
