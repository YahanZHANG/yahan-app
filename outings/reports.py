"""間違いを報告・情報を追加・写真を送る, from any trip, 子連れスポット or
event page. Everything lands in admin 「訂正・追加・写真」 and by email;
a photo shows only after an admin picks it."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import OutingsReport
from .photo_admin import DETAIL_URL, TARGETS, get_target
from .services.alerts import send_admin_alert
from .visitor import get_visitor_id, set_visitor_cookie

INTERVAL_SECONDS = 30


def title_of(target, obj):
    if target == "trip":
        return (obj.title_ja or obj.title_original).split("｜")[0]
    return getattr(obj, "title", "") or str(obj)


@require_POST
def send_report(request, target, pk):
    if target not in TARGETS:
        target = "kids"
    obj = get_target(target, pk)
    back = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        back = reverse(DETAIL_URL[target], args=[obj.pk])
    back = back.split("#")[0] + "#report"
    visitor_id = get_visitor_id(request)
    response = redirect(back)

    if request.POST.get("website"):
        return response  # bots fill the hidden field
    last = request.session.get("outings_report_sent_at", 0)
    if timezone.now().timestamp() - last < INTERVAL_SECONDS:
        messages.error(request, "少し時間をおいてから、もう一度送ってください。")
        return response

    kind = request.POST.get("kind", OutingsReport.Kind.FIX)
    if kind not in OutingsReport.Kind.values:
        kind = OutingsReport.Kind.FIX
    message = request.POST.get("message", "").strip()[:1000]
    photo_url = ""
    if request.FILES.get("photo"):
        try:
            from .services.user_event_cloudinary import upload_user_event_photo
            from .services.user_event_images import process_user_event_image
            processed = process_user_event_image(request.FILES["photo"], max_size=1600, quality=80)
            photo_url = upload_user_event_photo(processed, folder="yapp/outings/suggested", filename="photo.webp")
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            return response
        kind = OutingsReport.Kind.PHOTO
    if not message and not photo_url:
        messages.error(request, "内容を書くか、写真を選んでください。")
        return response

    report = OutingsReport.objects.create(
        target=target, object_id=obj.pk, kind=kind, message=message, photo_url=photo_url,
        visitor_id=visitor_id, user=request.user if request.user.is_authenticated else None,
    )
    request.session["outings_report_sent_at"] = timezone.now().timestamp()
    send_admin_alert(
        f"おでかけ：{report.get_kind_display()}（{title_of(target, obj)}）",
        f"{message}\n{photo_url}\n\n"
        + request.build_absolute_uri(reverse(DETAIL_URL[target], args=[obj.pk])) + "\n"
        + request.build_absolute_uri(reverse("admin:outings_outingsreport_changelist")),
    )
    messages.success(request, "ありがとうございます！管理者が確認します。" + ("写真は確認後に載せます。" if photo_url else ""))
    return set_visitor_cookie(request, response, visitor_id)
