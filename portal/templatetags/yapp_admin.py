from django import template


register = template.Library()


# ほとんど使わないアプリ。Admin では折りたたんでおき、必要なときだけ開く
RARE_APPS = ["board", "chat", "feeding", "recipes", "vaccination", "core"]


@register.simple_tag
def yapp_split_apps(app_list):
    """並び順はそのままで、ほとんど使わないアプリだけを分ける。"""

    return {
        "main": [app for app in app_list if app["app_label"] not in RARE_APPS],
        "rare": [app for app in app_list if app["app_label"] in RARE_APPS],
    }
