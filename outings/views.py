from datetime import datetime, time, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

from django.db import transaction

from django.db.models import Count, Prefetch, Q, Min, Max
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from django.core.exceptions import ValidationError

from .services.user_event_cloudinary import (
    upload_user_event_photo,
)

from .forms import EventSubmissionForm, OutingsCommentForm, OutingsFeedbackForm
from .services.alerts import send_admin_alert

from .models import (
    Event,
    EventCategory,
    EventLocation,
    EventOccurrence,
    EventTag,
    EventHeart, 
    OutingsPreference,
    OutingsComment,
    OutingsNotification
)

from .regions import REGION_CHOICES, clean_regions

from .visitor import get_visitor_id, set_visitor_cookie





def my_page(request):



    visitor_id = get_visitor_id(request)



    preference, created = (

        OutingsPreference.objects.get_or_create(

            visitor_id=visitor_id,

        )

    )



    hearted_events = (

        Event.objects.filter(

            hearts__visitor_id=visitor_id,

            status=Event.Status.PUBLISHED,

        )

        .select_related("location", "category")

        .order_by("-hearts__created_at")

    )



    my_post_count = 0

    unread_notification_count = 0



    if request.user.is_authenticated:



        my_post_count = Event.objects.filter(

            created_by=request.user,

        ).count()



        unread_notification_count = (

            OutingsNotification.objects.filter(

                recipient=request.user,

                is_read=False,

            ).count()

        )



    response = render(

        request,

        "outings/my_page.html",

        {

            "hearted_events": hearted_events,

            "heart_count": hearted_events.count(),

            "preference": preference,

            "my_post_count": my_post_count,

            "unread_notification_count": unread_notification_count,

        },

    )



    return set_visitor_cookie(

        request,

        response,

        visitor_id,

    )

# =========================================================
# Saved events
# =========================================================

def saved_events(request):

    visitor_id = get_visitor_id(request)

    hearted_events = (
        Event.objects.filter(
            hearts__visitor_id=visitor_id,
            status=Event.Status.PUBLISHED,
        )
        .select_related("location", "category")
        .order_by("-hearts__created_at")
    )

    response = render(
        request,
        "outings/saved_events.html",
        {
            "hearted_events": hearted_events,
        },
    )

    return set_visitor_cookie(
        request,
        response,
        visitor_id,
    )


# =========================================================
# My preferences
# =========================================================

def my_preferences(request):

    visitor_id = get_visitor_id(request)

    preference, created = (
        OutingsPreference.objects.get_or_create(
            visitor_id=visitor_id,
        )
    )

    regions = REGION_CHOICES

    response = render(
        request,
        "outings/my_preferences.html",
        {
            "preference": preference,
            "regions": regions,
        },
    )

    return set_visitor_cookie(
        request,
        response,
        visitor_id,
    )



@require_POST

def save_preferences(request):



    visitor_id = get_visitor_id(request)



    preference, created = (

        OutingsPreference.objects.get_or_create(

            visitor_id=visitor_id,

        )

    )



    regions = clean_regions(
        request.POST.getlist("regions")
    )



    preference.favorite_regions = regions

    preference.personalization_enabled = (

        request.POST.get("personalization") == "on"

    )

    preference.save()



    response = HttpResponseRedirect(
        reverse("outings:my_preferences")
    )



    return set_visitor_cookie(

        request,

        response,

        visitor_id,

    )





# =========================================================

# Notifications

# =========================================================



@login_required

def my_notifications(request):



    notifications = (

        OutingsNotification.objects.filter(

            recipient=request.user,

        )

        .select_related(

            "actor",

            "event",

        )

        .order_by("-created_at", "-pk")

    )



    paginator = Paginator(notifications, 20)



    page_obj = paginator.get_page(

        request.GET.get("page", 1)

    )



    return render(

        request,

        "outings/my_notifications.html",

        {

            "page_obj": page_obj,

        },

    )







@login_required

@require_POST

def notification_open(request, pk):



    notification = get_object_or_404(

        OutingsNotification.objects.select_related(

            "event",

            "comment",

        ),

        pk=pk,

        recipient=request.user,

    )



    if not notification.is_read:

        notification.is_read = True

        notification.save(

            update_fields=["is_read"]

        )



    event = notification.event



    if (

        event is None

        or event.status != Event.Status.PUBLISHED

    ):

        return redirect("outings:my_notifications")



    url = reverse(

        "outings:event_detail",

        kwargs={"pk": event.pk},

    )



    if notification.comment_id:

        url += f"#comment-{notification.comment_id}"



    return redirect(url)





# =========================================================
# Submit Event
# =========================================================

@login_required
def event_create(request):

    form = EventSubmissionForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
    )

    if request.method == "POST" and form.is_valid():

        # =================================================
        # Upload photo before database transaction
        # =================================================

        image_url = ""

        if form.cleaned_data.get("event_photo"):

            try:
                image_url = upload_user_event_photo(
                    form.processed_event_photo
                )

            except ValidationError as error:
                form.add_error(
                    "event_photo",
                    error,
                )

        # =================================================
        # Save only when there are no upload errors
        # =================================================

        if not form.errors:

            with transaction.atomic():

                location = EventLocation.objects.create(
                    name=form.cleaned_data["venue_name"],
                    address=form.cleaned_data["address"],
                    city=form.cleaned_data["city"],
                    canton=form.cleaned_data["canton"],
                )

                event = form.save(commit=False)

                event.location = location
                event.created_by = request.user

                # Member posts require approval.
                event.status = Event.Status.PENDING

                # Distinguish from imported events.
                event.source = None
                event.external_id = ""

                if image_url:
                    event.image_url = image_url

                event.save()
                form.save_m2m()

                EventOccurrence.objects.create(
                    event=event,
                    start_at=form.cleaned_data["start_at"],
                    end_at=form.cleaned_data["end_at"],
                )

            return redirect("outings:my_posts")

    return render(
        request,
        "outings/event_form.html",
        {
            "form": form,
        },
    )




# =========================================================

# My Event Posts

# =========================================================



@login_required

def my_posts(request):



    posts = (

        Event.objects.filter(

            created_by=request.user,

        )

        .select_related(

            "category",

            "location",

        )

        .order_by("-created_at", "-pk")

    )



    paginator = Paginator(posts, 20)



    page_obj = paginator.get_page(

        request.GET.get("page", 1)

    )



    return render(

        request,

        "outings/my_posts.html",

        {

            "page_obj": page_obj,

        },

    )







# =========================================================
# Edit own event
# =========================================================

def _owned_location(event, data):
    """Update the event's own location in place; create one if it is shared."""
    fields = {
        "name": data["venue_name"],
        "address": data["address"],
        "city": data["city"],
        "canton": data["canton"],
    }
    location = event.location
    if location and not location.events.exclude(pk=event.pk).exists():
        for key, value in fields.items():
            setattr(location, key, value)
        location.save()
        return location
    return EventLocation.objects.create(**fields)


@login_required
def event_edit(request, pk):

    event = get_object_or_404(
        Event,
        pk=pk,
        created_by=request.user,
    )

    if event.occurrences.count() != 1:

        return render(
            request,
            "outings/event_edit_unavailable.html",
            {"event": event},
        )

    form = EventSubmissionForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        instance=event,
    )

    if request.method == "POST" and form.is_valid():

        image_url = None

        # =================================================
        # New photo
        # =================================================

        if form.cleaned_data.get("event_photo"):

            try:
                image_url = upload_user_event_photo(
                    form.processed_event_photo
                )

            except ValidationError as error:
                form.add_error(
                    "event_photo",
                    error,
                )

        # =================================================
        # Save event
        # =================================================

        if not form.errors:

            with transaction.atomic():

                location = _owned_location(
                    event,
                    form.cleaned_data,
                )

                updated_event = form.save(
                    commit=False
                )

                updated_event.location = location
                updated_event.created_by = request.user

                # Editing requires re-approval.
                updated_event.status = Event.Status.PENDING

                if image_url:

                    # Replace existing photo.
                    updated_event.image_url = image_url

                elif form.cleaned_data.get(
                    "remove_photo"
                ):

                    # Remove existing photo.
                    updated_event.image_url = ""

                # Otherwise preserve existing image_url.

                updated_event.save()
                form.save_m2m()

                occurrence = (
                    updated_event.occurrences.get()
                )

                occurrence.start_at = (
                    form.cleaned_data["start_at"]
                )

                occurrence.end_at = (
                    form.cleaned_data["end_at"]
                )

                occurrence.save()

            return redirect("outings:my_posts")

    return render(
        request,
        "outings/event_form.html",
        {
            "form": form,
            "is_edit": True,
            "event": event,
        },
    )



# =========================================================

# Delete own event

# =========================================================



@login_required

def event_delete(request, pk):



    event = get_object_or_404(

        Event,

        pk=pk,

        created_by=request.user,

    )



    if request.method == "POST":

        event.delete()

        return redirect("outings:my_posts")



    return render(

        request,

        "outings/event_confirm_delete.html",

        {"event": event},

    )







# =========================================================

# Outings Comments

# =========================================================



@login_required

@require_POST

def comment_create(request, pk):



    event = get_object_or_404(

        Event,

        pk=pk,

        status=Event.Status.PUBLISHED,

    )



    parent_id = request.POST.get("parent", "").strip()

    parent = None



    if parent_id:

        parent = get_object_or_404(

            OutingsComment,

            pk=parent_id,

            event=event,

            parent__isnull=True,

            is_deleted=False,

        )



    form = OutingsCommentForm(request.POST)



    if not form.is_valid():

        messages.error(

            request,

            "コメントを確認して。500文字以内で入力してね。",

        )

        return redirect(

            reverse(

                "outings:event_detail",

                kwargs={"pk": event.pk},

            ) + "#comments"

        )



    # 30秒以内の連続コメントを制限

    recent_comment = OutingsComment.objects.filter(

        author=request.user,

        created_at__gte=(

            timezone.now() - timedelta(seconds=30)

        ),

    ).exists()



    if recent_comment:

        messages.error(

            request,

            "連続投稿を防ぐため、30秒以上空けて投稿して。",

        )

        return redirect(

            reverse(

                "outings:event_detail",

                kwargs={"pk": event.pk},

            ) + "#comments"

        )



    with transaction.atomic():



        comment = form.save(commit=False)

        comment.event = event

        comment.author = request.user

        comment.parent = parent

        comment.save()



        recipients = {}



        # イベント投稿者に通知

        if (

            event.created_by_id

            and event.created_by_id != request.user.pk

        ):

            recipients[event.created_by_id] = (

                OutingsNotification.Kind.COMMENT

            )



        # 返信先の作者に通知

        if (

            parent is not None

            and parent.author_id != request.user.pk

        ):

            recipients[parent.author_id] = (

                OutingsNotification.Kind.REPLY

            )



        for recipient_id, kind in recipients.items():



            OutingsNotification.objects.create(

                recipient_id=recipient_id,

                actor=request.user,

                event=event,

                comment=comment,

                kind=kind,

                message=(

                    "コメントに返信が届いた。"

                    if kind == OutingsNotification.Kind.REPLY

                    else "イベントに新しいコメントが届いた。"

                ),

            )



    return redirect(

        reverse(

            "outings:event_detail",

            kwargs={"pk": event.pk},

        ) + f"#comment-{comment.pk}"

    )





# =========================================================

# Edit own comment

# =========================================================



@login_required

def comment_edit(request, pk):



    comment = get_object_or_404(

        OutingsComment.objects.select_related("event"),

        pk=pk,

        author=request.user,

        is_deleted=False,

        event__status=Event.Status.PUBLISHED,

    )



    form = OutingsCommentForm(

        request.POST if request.method == "POST" else None,

        instance=comment,

    )



    if request.method == "POST" and form.is_valid():



        form.save()



        return redirect(

            reverse(

                "outings:event_detail",

                kwargs={"pk": comment.event_id},

            ) + f"#comment-{comment.pk}"

        )



    return render(

        request,

        "outings/comment_form.html",

        {

            "form": form,

            "comment": comment,

        },

    )





# =========================================================

# Soft delete comment

# =========================================================



@login_required

def comment_delete(request, pk):



    comment = get_object_or_404(

        OutingsComment.objects.select_related("event"),

        pk=pk,

        is_deleted=False,

        event__status=Event.Status.PUBLISHED,

    )



    event = comment.event



    can_delete = (

        request.user.pk == comment.author_id

        or request.user.pk == event.created_by_id

        or request.user.is_staff

    )



    if not can_delete:

        raise Http404



    if request.method == "POST":



        reason = request.POST.get(

            "reason", ""

        ).strip()[:200]



        if not reason:

            if request.user.pk == comment.author_id:

                reason = "本人による削除"

            elif request.user.is_staff:

                reason = "管理者による削除"

            else:

                reason = "イベント投稿者による削除"



        comment.is_deleted = True

        comment.deleted_at = timezone.now()

        comment.deleted_by = request.user

        comment.deleted_reason = reason



        comment.save(

            update_fields=[

                "is_deleted",

                "deleted_at",

                "deleted_by",

                "deleted_reason",

                "updated_at",

            ]

        )



        # 削除されたコメントを指す未読通知は既読化

        OutingsNotification.objects.filter(

            comment=comment,

            is_read=False,

        ).update(is_read=True)



        return redirect(

            reverse(

                "outings:event_detail",

                kwargs={"pk": event.pk},

            ) + f"#comment-{comment.pk}"

        )



    return render(

        request,

        "outings/comment_confirm_delete.html",

        {

            "comment": comment,

            "event": event,

        },

    )





# =========================================================

# My Comments

# =========================================================



@login_required

def my_comments(request):



    comments = (

        OutingsComment.objects.filter(

            author=request.user,

            is_deleted=False,

            event__status=Event.Status.PUBLISHED,

        )

        .select_related("event")

        .order_by("-created_at", "-pk")

    )



    paginator = Paginator(comments, 20)



    page_obj = paginator.get_page(

        request.GET.get("page", 1)

    )



    return render(

        request,

        "outings/my_comments.html",

        {

            "page_obj": page_obj,

        },

    )


# =========================================================
# About Outings
# =========================================================

FEEDBACK_INTERVAL_SECONDS = 60


def about_outings(request):
    form = OutingsFeedbackForm()
    if request.method == "POST":
        form = OutingsFeedbackForm(request.POST)
        last_sent = request.session.get("outings_feedback_sent_at", 0)
        url = reverse("outings:about_outings")
        if timezone.now().timestamp() - last_sent < FEEDBACK_INTERVAL_SECONDS:
            return redirect(f"{url}?sent=wait#feedback")
        if form.is_valid():
            if not form.cleaned_data.get("website"):
                feedback = form.save()
                send_admin_alert(
                    "新しいご意見・ご要望",
                    f"{feedback.message}\n\n"
                    + request.build_absolute_uri(reverse("admin:outings_outingsfeedback_changelist")),
                )
            request.session["outings_feedback_sent_at"] = timezone.now().timestamp()
            return redirect(f"{url}?sent=1#feedback")

    # Support methods are shared with Swiss News.
    return render(
        request,
        "outings/about.html",
        {
            "feedback_form": form,
            "feedback_sent": request.GET.get("sent", ""),
            "twint_url": getattr(settings, "SWISS_NEWS_TWINT_URL", ""),
            "bitcoin_address": getattr(settings, "SWISS_NEWS_BITCOIN_ADDRESS", ""),
        },
    )
