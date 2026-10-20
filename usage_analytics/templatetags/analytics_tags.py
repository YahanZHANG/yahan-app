from urllib.parse import urlencode

from django import template
from django.utils.html import format_html


register = template.Library()


@register.simple_tag
def delta(percent):
    """前の期間との増減バッジ。"""

    if percent is None:
        return format_html('<span class="ya-delta">前の期間なし</span>')

    if percent > 0:
        return format_html('<span class="ya-delta is-up">▲ {}%</span>', percent)

    if percent < 0:
        return format_html('<span class="ya-delta is-down">▼ {}%</span>', -percent)

    return format_html('<span class="ya-delta">± 0%</span>')


@register.simple_tag
def scope_query(scope, **overrides):
    """期間・アプリの切り替えリンク用の ?days=..&app=.."""

    params = {"days": scope.days, "app": scope.app}
    params.update(overrides)

    return "?" + urlencode({key: value for key, value in params.items() if value})
