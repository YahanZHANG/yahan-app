from datetime import timedelta
import json

import mimetypes
from pathlib import Path

from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import FileResponse, Http404, JsonResponse
from django.db import transaction

from collections import defaultdict
from decimal import Decimal

from .forms import (
    BabyGrowthNoteForm,
    BabyLogForm,
    ExpenseForm,
    FamilyStatusForm,
    MeetingNoteForm,
    MilkLogForm,
    PoopLogForm,
    ScheduleForm,
    SleepLogForm,
    TaskForm,
)

from .models import (
    BabyGrowthNote,
    BabyLog,
    Expense,
    ExpenseShare,
    FamilyStatus,
    ImportantNotice,
    MeetingNote,
    MilkLog,
    PoopLog,
    Schedule,
    SharedLocation,
    SleepLog,
    Task,
    TravelGroup,
    UserProfile,
)

def get_current_travel_group(request):
    """
    ログインユーザーが現在選択している旅行を返す。
    選択されていなければ、参加している最初の旅行を使用する。
    """

    travel_groups = TravelGroup.objects.filter(
        members=request.user,
    ).distinct()

    if not travel_groups.exists():
        return None

    current_group_id = request.session.get(
        "current_travel_group_id"
    )

    if current_group_id:
        current_group = travel_groups.filter(
            id=current_group_id,
        ).first()

        if current_group:
            return current_group

    current_group = travel_groups.first()

    request.session[
        "current_travel_group_id"
    ] = current_group.id

    return current_group

@login_required
def switch_travel_group(
    request,
    travel_group_id,
):
    travel_group = get_object_or_404(
        TravelGroup,
        id=travel_group_id,
        members=request.user,
    )

    request.session[
        "current_travel_group_id"
    ] = travel_group.id

    return redirect(
        "travel:home",
    )

@login_required
def travel_group_list(request):
    travel_groups = TravelGroup.objects.filter(
        members=request.user,
    ).select_related(
        "owner",
    ).distinct()

    return render(
        request,
        "travel/travel_group_list.html",
        {
            "travel_groups": travel_groups,
        },
    )

@login_required
def travel_group_create(request):
    if request.method == "POST":
        name = request.POST.get(
            "name",
            "",
        ).strip()

        if name:
            travel_group = TravelGroup.objects.create(
                name=name,
                owner=request.user,
            )

            travel_group.members.add(
                request.user
            )

            request.session[
                "current_travel_group_id"
            ] = travel_group.id

            return redirect(
                "travel:home",
            )

    return render(
        request,
        "travel/travel_group_create.html",
    )

@login_required
def travel_group_settings(
    request,
    travel_group_id,
):
    travel_group = get_object_or_404(
        TravelGroup.objects.select_related(
            "owner",
        ).prefetch_related(
            "members",
        ),
        id=travel_group_id,
        members=request.user,
    )

    return render(
        request,
        "travel/travel_group_settings.html",
        {
            "travel_group": travel_group,
            "is_owner": (
                travel_group.owner_id
                == request.user.id
            ),
        },
    )

@login_required
def travel_group_member_add(
    request,
    travel_group_id,
):
    travel_group = get_object_or_404(
        TravelGroup,
        id=travel_group_id,
        owner=request.user,
    )

    if request.method != "POST":
        return redirect(
            "travel:travel_group_settings",
            travel_group_id=travel_group.id,
        )

    username = request.POST.get(
        "username",
        "",
    ).strip()

    if username:
        User = get_user_model()

        user = User.objects.filter(
            username=username,
            is_active=True,
        ).first()

        if user:
            travel_group.members.add(
                user
            )

    return redirect(
        "travel:travel_group_settings",
        travel_group_id=travel_group.id,
    )

@login_required
def home(request):
    current_travel_group = get_current_travel_group(
        request
    )

    if current_travel_group is None:
        return render(
            request,
            "travel/no_travel_group.html",
        )

    today = timezone.localdate()

    arrival_date = timezone.datetime(
        2026,
        8,
        16,
    ).date()

    stay_day = (
        today - arrival_date
    ).days

    upcoming_schedules = Schedule.objects.filter(
        travel_group=current_travel_group,
        start_at__gte=timezone.now(),
    ).select_related(
        "created_by",
    ).order_by(
        "start_at",
    )[:2]

    tasks = Task.objects.filter(
        travel_group=current_travel_group,
    ).order_by(
        "is_completed",
        "due_at",
        "-created_at",
    )[:5]

    latest_milk = MilkLog.objects.filter(
        travel_group=current_travel_group,
    ).first()

    latest_sleep = SleepLog.objects.filter(
        travel_group=current_travel_group,
        ended_at__isnull=False,
    ).order_by(
        "-started_at",
    ).first()

    active_sleep = SleepLog.objects.filter(
        travel_group=current_travel_group,
        ended_at__isnull=True,
    ).order_by(
        "-started_at",
    ).first()
    
    latest_poop = PoopLog.objects.filter(
        travel_group=current_travel_group,
    ).first()

    User = get_user_model()

    family_users = User.objects.filter(
        is_active=True,
        is_superuser=False,
    ).select_related(
        "profile",
    ).order_by(
        "username",
    )

    family_cards = []

    for user in family_users:
        family_status = FamilyStatus.objects.filter(
            user=user,
        ).first()

        shared_location = SharedLocation.objects.filter(
            user=user,
        ).first()

        family_cards.append(
            {
                "user": user,
                "status": family_status,
                "location": shared_location,
            }
        )

    map_locations = []

    for card in family_cards:
        location = card["location"]

        if not location:
            continue

        user = card["user"]

        display_name = (
            user.first_name
            if user.first_name
            else user.username
        )

        shared_at = timezone.localtime(location.shared_at)

        map_locations.append(
            {
                "user_id": user.id,
                "name": display_name,
                "label": display_name[:1],
                "latitude": float(location.latitude),
                "longitude": float(location.longitude),
                "accuracy": location.accuracy,
                "shared_at": (
                    f"{shared_at.month}月"
                    f"{shared_at.day}日 "
                    f"{shared_at:%H:%M}"
                ),
            }
        )

    important_notice = ImportantNotice.objects.filter(
        travel_group=current_travel_group,
        is_active=True,
    ).first()

    latest_meeting_note = MeetingNote.objects.filter(
        travel_group=current_travel_group,
    ).select_related(
        "created_by",
    ).first()

    latest_growth_notes = BabyGrowthNote.objects.filter(
        travel_group=current_travel_group,
    ).select_related(
        "created_by",
    )[:5]

    context = {
        "today": today,
        "current_travel_group": current_travel_group,
        "travel_groups": TravelGroup.objects.filter(
            members=request.user,
        ).distinct(),
        "stay_day": stay_day,
        "upcoming_schedules": upcoming_schedules,
        "latest_growth_notes": latest_growth_notes,
        "tasks": tasks,
        "latest_milk": latest_milk,
        "latest_sleep": latest_sleep,
        "active_sleep": active_sleep,
        "latest_poop": latest_poop,
        "family_cards": family_cards,
        "map_locations": map_locations,
        "important_notice": important_notice,
        "latest_meeting_note": latest_meeting_note,
    }

    return render(
        request,
        "travel/home.html",
        context,
    )

@login_required
def schedule_create(request):
    if request.method == "POST":
        form = ScheduleForm(request.POST)

        if form.is_valid():
            schedule = form.save(commit=False)

            schedule.created_by = request.user
            schedule.travel_group = get_current_travel_group(
                request
            )

            schedule.save()
            form.save_m2m()

            return redirect(
                "travel:schedule_list"
            )

    else:
        form = ScheduleForm()

    return render(
        request,
        "travel/form.html",
        {
            "form": form,
            "page_title": "予定を追加",
            "submit_label": "予定を保存",
        },
    )

@login_required
def schedule_update(request, schedule_id):
    current_travel_group = get_current_travel_group(
        request
    )

    schedule = get_object_or_404(
        Schedule,
        id=schedule_id,
        travel_group=current_travel_group,
    )

    if request.method == "POST":
        form = ScheduleForm(
            request.POST,
            instance=schedule,
        )

        if form.is_valid():
            form.save()
            return redirect("travel:home")
    else:
        form = ScheduleForm(
            instance=schedule,
        )

    return render(
        request,
        "travel/form.html",
        {
            "form": form,
            "page_title": "予定を編集",
            "submit_label": "変更を保存",
        },
    )

@login_required
def schedule_list(request):
    current_travel_group = get_current_travel_group(
        request
    )

    upcoming_schedules = Schedule.objects.filter(
        travel_group=current_travel_group,
        start_at__gte=timezone.now(),
    ).select_related(
        "created_by",
    ).order_by(
        "start_at",
    )

    return render(
        request,
        "travel/schedule_list.html",
        {
            "upcoming_schedules": upcoming_schedules,
            "current_travel_group": current_travel_group,
        },
    )

@login_required
def schedule_delete(request, schedule_id):
    current_travel_group = get_current_travel_group(
        request
    )

    schedule = get_object_or_404(
        Schedule,
        id=schedule_id,
        travel_group=current_travel_group,
    )

    if request.method == "POST":
        schedule.delete()

        return redirect(
            "travel:schedule_list",
        )

    return render(
        request,
        "travel/schedule_confirm_delete.html",
        {
            "schedule": schedule,
        },
    )

@login_required
def task_create(request):
    if request.method == "POST":
        form = TaskForm(request.POST)

        if form.is_valid():
            task = form.save(commit=False)

            task.created_by = request.user
            task.travel_group = get_current_travel_group(
                request
            )

            task.save()

            return redirect(
                "travel:home"
            )
            return redirect("travel:home")
    else:
        form = TaskForm()

    return render(
        request,
        "travel/form.html",
        {
            "form": form,
            "page_title": "お願いを追加",
            "submit_label": "お願いを保存",
        },
    )

@login_required
def task_toggle(request, task_id):
    if request.method == "POST":
        current_travel_group = get_current_travel_group(
            request
        )

        task = get_object_or_404(
            Task,
            id=task_id,
            travel_group=current_travel_group,
        )

        task.is_completed = not task.is_completed
        task.save(
            update_fields=[
                "is_completed",
                "updated_at",
            ]
        )

    return redirect("travel:home")

@login_required
def task_list(request):
    current_travel_group = get_current_travel_group(
        request
    )

    incomplete_tasks = Task.objects.filter(
        travel_group=current_travel_group,
        is_completed=False,
    ).select_related(
        "created_by",
    ).order_by(
        "due_at",
        "-created_at",
    )

    completed_tasks = Task.objects.filter(
        travel_group=current_travel_group,
        is_completed=True,
    ).select_related(
        "created_by",
    ).order_by(
        "-updated_at",
    )

    return render(
        request,
        "travel/task_list.html",
        {
            "incomplete_tasks": incomplete_tasks,
            "completed_tasks": completed_tasks,
            "current_travel_group": current_travel_group,
        },
    )

@login_required
def task_update(request, task_id):
    current_travel_group = get_current_travel_group(
        request
    )

    task = get_object_or_404(
        Task,
        id=task_id,
        travel_group=current_travel_group,
    )

    if request.method == "POST":
        form = TaskForm(
            request.POST,
            instance=task,
        )

        if form.is_valid():
            form.save()
            return redirect(
                "travel:task_list",
            )
    else:
        form = TaskForm(
            instance=task,
        )

    return render(
        request,
        "travel/form.html",
        {
            "form": form,
            "page_title": "お願いを編集",
            "submit_label": "変更を保存",
        },
    )


@login_required
def task_delete(request, task_id):
    current_travel_group = get_current_travel_group(
        request
    )

    task = get_object_or_404(
        Task,
        id=task_id,
        travel_group=current_travel_group,
    )

    if request.method == "POST":
        task.delete()

        return redirect(
            "travel:task_list",
        )

    return render(
        request,
        "travel/task_confirm_delete.html",
        {
            "task": task,
        },
    )

@login_required
def baby_log_create(request):
    if request.method == "POST":
        form = BabyLogForm(request.POST)

        if form.is_valid():
            baby_log = form.save(commit=False)

            baby_log.created_by = request.user
            baby_log.travel_group = get_current_travel_group(
                request
            )

            baby_log.save()

            return redirect(
                "travel:home"
            )
    else:
        form = BabyLogForm()

    return render(
        request,
        "travel/form.html",
        {
            "form": form,
            "page_title": "赤ちゃん記録を追加",
            "submit_label": "記録を保存",
        },
    )

@login_required
def family_status_update(request):
    family_status, created = FamilyStatus.objects.get_or_create(
        user=request.user,
    )

    if request.method == "POST":
        form = FamilyStatusForm(
            request.POST,
            instance=family_status,
        )

        if form.is_valid():
            form.save()
            return redirect("travel:home")
    else:
        form = FamilyStatusForm(
            instance=family_status,
        )

    return render(
        request,
        "travel/form.html",
        {
            "form": form,
            "page_title": "自分の状態を変更",
            "submit_label": "状態を更新",
        },
    )

@login_required
def milk_log_create(request):
    if request.method == "POST":
        form = MilkLogForm(request.POST)

        if form.is_valid():
            milk_log = form.save(commit=False)

            milk_log.created_by = request.user
            milk_log.travel_group = get_current_travel_group(
                request
            )

            milk_log.save()

            return redirect("travel:home")
    else:
        form = MilkLogForm()

    return render(
        request,
        "travel/form.html",
        {
            "form": form,
            "page_title": "ミルクを記録",
            "submit_label": "ミルク記録を保存",
        },
    )

@login_required
def sleep_log_create(request):
    if request.method == "POST":
        form = SleepLogForm(request.POST)

        if form.is_valid():
            sleep_log = form.save(commit=False)

            sleep_log.created_by = request.user
            sleep_log.travel_group = get_current_travel_group(
                request
            )

            sleep_log.save()

            return redirect(
                "travel:home"
            )
    else:
        form = SleepLogForm()

    return render(
        request,
        "travel/form.html",
        {
            "form": form,
            "page_title": "睡眠を記録",
            "submit_label": "睡眠記録を保存",
        },
    )

@login_required
def poop_log_create(request):
    if request.method == "POST":
        form = PoopLogForm(request.POST)

        if form.is_valid():
            poop_log = form.save(commit=False)

            poop_log.created_by = request.user
            poop_log.travel_group = get_current_travel_group(
                request
            )

            poop_log.save()

            return redirect(
                "travel:home"
            )
    else:
        form = PoopLogForm()

    return render(
        request,
        "travel/form.html",
        {
            "form": form,
            "page_title": "うんちを記録",
            "submit_label": "うんち記録を保存",
        },
    )

@login_required
def meeting_note_create(request):
    if request.method == "POST":
        form = MeetingNoteForm(request.POST)

        if form.is_valid():
            meeting_note = form.save(
                commit=False,
            )

            meeting_date = timezone.localtime(
                meeting_note.discussed_at
            )

            meeting_note.title = (
                f"{meeting_date.year}年"
                f"{meeting_date.month}月"
                f"{meeting_date.day}日の家族会議"
            )

            meeting_note.created_by = request.user
            meeting_note.travel_group = get_current_travel_group(
                request
            )

            meeting_note.save()

            return redirect("travel:home")
    else:
        form = MeetingNoteForm()

    return render(
        request,
        "travel/form.html",
        {
            "form": form,
            "page_title": "家族会議メモを追加",
            "submit_label": "メモを保存",
        },
    )

@login_required
def meeting_note_update(request, note_id):
    current_travel_group = get_current_travel_group(
        request
    )

    meeting_note = get_object_or_404(
        MeetingNote,
        id=note_id,
        travel_group=current_travel_group,
    )

    if request.method == "POST":
        form = MeetingNoteForm(
            request.POST,
            instance=meeting_note,
        )

        if form.is_valid():
            meeting_note = form.save(
                commit=False,
            )

            meeting_date = timezone.localtime(
                meeting_note.discussed_at
            )

            meeting_note.title = (
                f"{meeting_date.year}年"
                f"{meeting_date.month}月"
                f"{meeting_date.day}日の家族会議"
            )

            meeting_note.save()

            return redirect(
                "travel:meeting_note_list",
            )
    else:
        form = MeetingNoteForm(
            instance=meeting_note,
        )

    return render(
        request,
        "travel/form.html",
        {
            "form": form,
            "page_title": "家族会議メモを編集",
            "submit_label": "変更を保存",
        },
    )

@login_required
def meeting_note_delete(request, note_id):
    current_travel_group = get_current_travel_group(
        request
    )

    meeting_note = get_object_or_404(
        MeetingNote,
        id=note_id,
        travel_group=current_travel_group,
    )

    if request.method == "POST":
        meeting_note.delete()

        return redirect(
            "travel:meeting_note_list",
        )

    return render(
        request,
        "travel/meeting_note_confirm_delete.html",
        {
            "meeting_note": meeting_note,
        },
    )

@login_required
def share_location(request):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "error": "POSTリクエストが必要です。",
            },
            status=405,
        )

    try:
        data = json.loads(request.body)

        latitude = data.get("latitude")
        longitude = data.get("longitude")
        accuracy = data.get("accuracy")

        if latitude is None or longitude is None:
            return JsonResponse(
                {
                    "success": False,
                    "error": "緯度または経度がありません。",
                },
                status=400,
            )

        shared_location, created = SharedLocation.objects.update_or_create(
            user=request.user,
            defaults={
                "latitude": latitude,
                "longitude": longitude,
                "accuracy": (
                    round(accuracy)
                    if accuracy is not None
                    else None
                ),
            },
        )

        return JsonResponse(
            {
                "success": True,
                "shared_at": shared_location.shared_at.isoformat(),
                "google_maps_url": shared_location.google_maps_url,
            }
        )

    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse(
            {
                "success": False,
                "error": "位置情報を正しく保存できませんでした。",
            },
            status=400,
        )

@login_required
def milk_log_quick_create(request, amount_ml):
    allowed_amounts = {150, 200}

    if request.method != "POST":
        return redirect("travel:home")

    if amount_ml not in allowed_amounts:
        return redirect("travel:home")

    MilkLog.objects.create(
        travel_group=get_current_travel_group(
            request
        ),
        fed_at=timezone.now(),
        amount_ml=amount_ml,
        created_by=request.user,
    )

    return redirect("travel:home")

@login_required
def sleep_start(request):
    if request.method != "POST":
        return redirect(
            "travel:home"
        )

    current_travel_group = get_current_travel_group(
        request
    )

    active_sleep = SleepLog.objects.filter(
        travel_group=current_travel_group,
        ended_at__isnull=True,
    ).first()

    if active_sleep is None:
        SleepLog.objects.create(
            travel_group=current_travel_group,
            started_at=timezone.now(),
            created_by=request.user,
        )

    return redirect(
        "travel:home"
    )

@login_required
def sleep_end(request):
    if request.method != "POST":
        return redirect(
            "travel:home"
        )

    current_travel_group = get_current_travel_group(
        request
    )

    active_sleep = SleepLog.objects.filter(
        travel_group=current_travel_group,
        ended_at__isnull=True,
    ).order_by(
        "-started_at",
    ).first()

    if active_sleep is not None:
        active_sleep.ended_at = timezone.now()

        active_sleep.save(
            update_fields=[
                "ended_at",
            ]
        )

    return redirect(
        "travel:home"
    )

@login_required
def profile_photo(request, user_id):
    """
    Persistent Diskに保存された家族プロフィール写真を返す。
    ログイン済みユーザーだけが閲覧できる。
    """

    User = get_user_model()

    user = get_object_or_404(
        User.objects.select_related("profile"),
        id=user_id,
        is_active=True,
    )

    try:
        photo = user.profile.photo
    except UserProfile.DoesNotExist:
        raise Http404(
            "プロフィール写真がありません。"
        )

    if not photo:
        raise Http404(
            "プロフィール写真がありません。"
        )

    media_root = Path(
        settings.MEDIA_ROOT
    ).resolve()

    photo_path = Path(
        photo.path
    ).resolve()

    try:
        photo_path.relative_to(
            media_root
        )
    except ValueError:
        raise Http404(
            "無効な画像パスです。"
        )

    if not photo_path.is_file():
        raise Http404(
            "プロフィール写真が見つかりません。"
        )

    content_type, _ = mimetypes.guess_type(
        photo_path.name
    )

    return FileResponse(
        open(
            photo_path,
            "rb",
        ),
        content_type=(
            content_type
            or "application/octet-stream"
        ),
    )

def save_expense_shares(
    expense,
    cleaned_data,
    travel_group,
):
    """旅行メンバーごとの負担額を保存する。"""

    members = travel_group.members.filter(
        is_active=True,
    )

    member_ids = []

    for member in members:
        member_ids.append(
            member.id
        )

        field_name = (
            f"share_user_{member.id}"
        )

        amount = cleaned_data.get(
            field_name,
            Decimal("0"),
        )

        if amount and amount > 0:
            ExpenseShare.objects.update_or_create(
                expense=expense,
                user=member,
                defaults={
                    "amount": amount,
                },
            )
        else:
            ExpenseShare.objects.filter(
                expense=expense,
                user=member,
            ).delete()

    ExpenseShare.objects.filter(
        expense=expense,
    ).exclude(
        user_id__in=member_ids,
    ).delete()

@login_required
def expense_create(request):
    current_travel_group = get_current_travel_group(
        request
    )

    if request.method == "POST":
        form = ExpenseForm(
            request.POST,
            travel_group=current_travel_group,
        )

        if form.is_valid():
            with transaction.atomic():
                expense = form.save(
                    commit=False,
                )

                expense.created_by = request.user
                expense.travel_group = (
                    current_travel_group
                )

                expense.save()

                save_expense_shares(
                    expense,
                    form.cleaned_data,
                    current_travel_group,
                )

            return redirect(
                "travel:expense_list",
            )

    else:
        form = ExpenseForm(
            travel_group=current_travel_group,
        )

    return render(
        request,
        "travel/expense_form.html",
        {
            "form": form,
            "page_title": "支出を追加",
            "submit_label": "保存",
            "current_travel_group": (
                current_travel_group
            ),
        },
    )

@login_required
def expense_update(
    request,
    expense_id,
):
    current_travel_group = get_current_travel_group(
        request
    )

    expense = get_object_or_404(
        Expense,
        id=expense_id,
        travel_group=current_travel_group,
    )

    if request.method == "POST":
        form = ExpenseForm(
            request.POST,
            instance=expense,
            travel_group=current_travel_group,
        )

        if form.is_valid():
            with transaction.atomic():
                expense = form.save()

                save_expense_shares(
                    expense,
                    form.cleaned_data,
                    current_travel_group,
                )

            return redirect(
                "travel:expense_list",
            )

    else:
        form = ExpenseForm(
            instance=expense,
            travel_group=current_travel_group,
        )

    return render(
        request,
        "travel/expense_form.html",
        {
            "form": form,
            "expense": expense,
            "page_title": "支出を編集",
            "submit_label": "変更を保存",
            "current_travel_group": (
                current_travel_group
            ),
        },
    )


@login_required
def expense_delete(request, expense_id):
    current_travel_group = get_current_travel_group(
        request
    )

    expense = get_object_or_404(
        Expense,
        id=expense_id,
        travel_group=current_travel_group,
    )

    if request.method == "POST":
        expense.delete()
        return redirect("travel:expense_list")

    return render(
        request,
        "travel/expense_confirm_delete.html",
        {
            "expense": expense,
        },
    )

def calculate_settlement_for_currency(
    users,
    expenses,
    currency,
):
    """
    指定通貨について、各ユーザーの残高と
    必要な送金一覧を計算する。
    """

    balances = {
        user.id: Decimal("0.00")
        for user in users
    }

    user_map = {
        user.id: user
        for user in users
    }

    currency_expenses = [
        expense
        for expense in expenses
        if expense.currency == currency
    ]

    # 実際に支払った金額を加算する
    for expense in currency_expenses:
        if expense.paid_by_id in balances:
            balances[expense.paid_by_id] += (
                expense.total_amount
            )

        # 本人が負担する金額を差し引く
        for share in expense.shares.all():
            if share.user_id in balances:
                balances[share.user_id] -= share.amount

    creditors = []
    debtors = []

    for user_id, balance in balances.items():
        if balance > 0:
            creditors.append(
                {
                    "user": user_map[user_id],
                    "amount": balance,
                }
            )
        elif balance < 0:
            debtors.append(
                {
                    "user": user_map[user_id],
                    "amount": -balance,
                }
            )

    # 金額が大きい順に並べる
    creditors.sort(
        key=lambda item: item["amount"],
        reverse=True,
    )

    debtors.sort(
        key=lambda item: item["amount"],
        reverse=True,
    )

    transfers = []

    creditor_index = 0
    debtor_index = 0

    while (
        creditor_index < len(creditors)
        and debtor_index < len(debtors)
    ):
        creditor = creditors[creditor_index]
        debtor = debtors[debtor_index]

        transfer_amount = min(
            creditor["amount"],
            debtor["amount"],
        )

        if transfer_amount > 0:
            transfers.append(
                {
                    "from_user": debtor["user"],
                    "to_user": creditor["user"],
                    "amount": transfer_amount,
                }
            )

        creditor["amount"] -= transfer_amount
        debtor["amount"] -= transfer_amount

        if creditor["amount"] == 0:
            creditor_index += 1

        if debtor["amount"] == 0:
            debtor_index += 1

    result_balances = []

    for user in users:
        result_balances.append(
            {
                "user": user,
                "balance": balances[user.id],
            }
        )

    return {
        "currency": currency,
        "balances": result_balances,
        "transfers": transfers,
        "expense_count": len(currency_expenses),
    }

@login_required
def expense_list(request):
    current_travel_group = get_current_travel_group(
        request
    )

    expenses = Expense.objects.filter(
        travel_group=current_travel_group,
    ).select_related(
        "paid_by",
        "created_by",
    ).prefetch_related(
        "shares__user",
    ).order_by(
        "-paid_at",
        "-id",
    )

    return render(
        request,
        "travel/expense_list.html",
        {
            "expenses": expenses,
            "current_travel_group": current_travel_group,
        },
    )

@login_required
def expense_settlement(request):
    current_travel_group = get_current_travel_group(
        request
    )

    users = list(
        current_travel_group.members.filter(
            is_active=True,
        ).order_by(
            "username",
        )
    )

    expenses = list(
        Expense.objects.filter(
            travel_group=current_travel_group,
        ).select_related(
            "paid_by",
        ).prefetch_related(
            "shares__user",
        )
    )

    used_currencies = sorted(
        {
            expense.currency
            for expense in expenses
        }
    )

    settlement_groups = []

    for currency in used_currencies:
        group = calculate_settlement_for_currency(
            users=users,
            expenses=expenses,
            currency=currency,
        )

        settlement_groups.append(group)

    return render(
        request,
        "travel/expense_settlement.html",
        {
            "settlement_groups": settlement_groups,
            "current_travel_group": current_travel_group,
        },
    )

@login_required
def baby_growth_note_create(request):
    if request.method == "POST":
        form = BabyGrowthNoteForm(
            request.POST,
        )

        if form.is_valid():
            note = form.save(
                commit=False,
            )

            note.created_by = request.user
            note.travel_group = get_current_travel_group(
                request
            )

            note.save()

            return redirect(
                "travel:baby_growth_note_list",
            )
    else:
        form = BabyGrowthNoteForm()

    return render(
        request,
        "travel/baby_growth_note_form.html",
        {
            "form": form,
        },
    )

@login_required
def baby_growth_note_list(request):
    current_travel_group = get_current_travel_group(
        request
    )

    growth_notes = BabyGrowthNote.objects.filter(
        travel_group=current_travel_group,
    ).select_related(
        "created_by",
    )

    return render(
        request,
        "travel/baby_growth_note_list.html",
        {
            "growth_notes": growth_notes,
            "current_travel_group": current_travel_group,
        },
    )

@login_required
def baby_growth_note_update(request, note_id):
    current_travel_group = get_current_travel_group(
        request
    )

    note = get_object_or_404(
        BabyGrowthNote,
        id=note_id,
        travel_group=current_travel_group,
    )

    if request.method == "POST":
        form = BabyGrowthNoteForm(
            request.POST,
            instance=note,
        )

        if form.is_valid():
            form.save()
            return redirect("travel:baby_growth_note_list")
    else:
        form = BabyGrowthNoteForm(
            instance=note,
        )

    return render(
        request,
        "travel/form.html",
        {
            "form": form,
            "page_title": "成長メモを編集",
            "submit_label": "変更を保存",
        },
    )

@login_required
def baby_growth_note_delete(request, note_id):
    current_travel_group = get_current_travel_group(
        request
    )

    note = get_object_or_404(
        BabyGrowthNote,
        id=note_id,
        travel_group=current_travel_group,
    )

    if request.method == "POST":
        note.delete()

        return redirect(
            "travel:baby_growth_note_list",
        )

    return render(
        request,
        "travel/baby_growth_note_confirm_delete.html",
        {
            "note": note,
        },
    )

@login_required
def meeting_note_list(request):
    current_travel_group = get_current_travel_group(
        request
    )

    meeting_notes = MeetingNote.objects.filter(
        travel_group=current_travel_group,
    ).select_related(
        "created_by",
    ).order_by(
        "-discussed_at",
        "-id",
    )

    return render(
        request,
        "travel/meeting_note_list.html",
        {
            "meeting_notes": meeting_notes,
            "current_travel_group": current_travel_group,
        },
    )