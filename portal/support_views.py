"""Yapp-wide support page, shared by every app (Swiss News, おでかけ, ...).

Apps link here with ?from=<app> so the page can link back and the admin
email says which app the supporter came from.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse

from news.forms import SupportContactForm
from news.models import SupportRequest


APPS = {
    "news": ("Swiss News", "news:home"),
    "outings": ("おでかけ", "outings:home"),
    "washoku": ("スイスで和食", "washoku:home"),
}

METHODS = {
    "bank": {
        "title": "銀行口座で応援する",
        "description": "ありがとうございます！振込先をメールでご案内しますので、必要事項を入力してください。",
    },
    "other": {
        "title": "その他の方法で応援する",
        "description": "ありがとうございます！ご希望の応援方法を教えてください。",
    },
}


def _origin(request):
    key = request.GET.get("from", "") or request.POST.get("from", "")
    if key not in APPS:
        return None
    name, url_name = APPS[key]
    return {"key": key, "name": name, "url": reverse(url_name)}


def support(request):
    return render(request, "portal/support.html", {
        "origin": _origin(request),
        "twint_url": getattr(settings, "SWISS_NEWS_TWINT_URL", ""),
        "twint_phone": getattr(settings, "YAPP_TWINT_PHONE", ""),
        "bitcoin_address": getattr(settings, "SWISS_NEWS_BITCOIN_ADDRESS", ""),
        "sent": request.GET.get("sent") == "1",
    })


def support_contact(request, method):
    if method not in METHODS:
        return redirect("portal:support")
    origin = _origin(request)
    form = SupportContactForm(request.POST or None, support_method=method)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        support_request = SupportRequest.objects.create(
            method=method,
            bank_country=data.get("bank_country") or "",
            name=data.get("name") or "",
            email=data["email"],
            message=data.get("message") or "",
        )
        app_name = origin["name"] if origin else "Yapp"
        recipient = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", "")
        if recipient:
            send_mail(
                subject=f"【Yapp】応援の問い合わせ（{app_name}から）",
                message=(
                    f"{app_name}から応援の問い合わせが届きました。\n\n"
                    f"方法：{support_request.get_method_display()}\n"
                    f"氏名：{support_request.name or '未入力'}\n"
                    f"メール：{support_request.email}\n"
                    f"希望口座：{support_request.bank_country or 'なし'}\n\n"
                    f"メッセージ：\n{support_request.message or 'なし'}\n\n"
                    "Yapp Adminから内容を確認してください。"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=True,
            )
        url = reverse("portal:support") + "?sent=1"
        if origin:
            url += f"&from={origin['key']}"
        return redirect(url)
    return render(request, "portal/support_contact.html", {
        "form": form,
        "method": method,
        "config": METHODS[method],
        "origin": origin,
    })


FEEDBACK_URLS = {
    "news": "news:about",
    "washoku": "washoku:about",
}


def help_page(request):
    """困ったときは (ログインできない・ページが開けない など)。全アプリ共通。"""

    origin = _origin(request)
    feedback_url = None
    if origin and origin["key"] in FEEDBACK_URLS:
        feedback_url = reverse(FEEDBACK_URLS[origin["key"]]) + "#feedback"

    return render(request, "portal/help.html", {
        "origin": origin,
        "feedback_url": feedback_url or reverse("news:about") + "#feedback",
    })
