from django import template

from config.pwa import icons_for_path
from portal.models import AppPopup

register = template.Library()


@register.inclusion_tag("includes/app_popup.html", takes_context=True)
def app_popup(context):
    """
    アプリを開いたときのポップアップ (管理画面「ポップアップ（各アプリ）」)。
    スタッフは ?popup_preview=<番号> で、出す設定でなくても確認できる。
    """

    request = context.get("request")
    if request is None:
        return {"popups": []}
    color = icons_for_path(request.path)["theme_color"]

    preview = request.GET.get("popup_preview", "")
    if preview.isdigit() and request.user.is_staff:
        return {"popups": list(AppPopup.objects.filter(pk=int(preview))), "preview": True, "color": color}

    try:
        popups = AppPopup.for_request(request)
    except Exception:
        # テーブルがまだない (migrate 前) ときなどでも、ページは出す
        popups = []
    return {"popups": popups, "preview": False, "color": color}
