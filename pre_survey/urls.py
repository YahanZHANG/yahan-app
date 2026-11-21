from functools import wraps

from django.conf import settings
from django.urls import path

from . import views


def _to_board(view):
    """2026-11-21: 掲示板が一般公開になったので、事前アンケートはすべて掲示板へ転送する。
    (PRE_SURVEY_CLOSED=false で元に戻せる。管理画面の集計は /admin/ のまま使える)"""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if getattr(settings, "PRE_SURVEY_CLOSED", True):
            return views.to_board(request)
        return view(request, *args, **kwargs)

    return wrapper


app_name = "pre_survey"

urlpatterns = [
    path("", _to_board(views.start), name="start"),
    path("nickname/", _to_board(views.nickname), name="nickname"),
    path("themes/", _to_board(views.themes), name="themes"),
    path("wish/", _to_board(views.wish), name="wish"),
    path("q/", _to_board(views.question), name="question"),
    path("q/<int:pk>/", _to_board(views.question_action), name="question_action"),
    path("q/<int:pk>/undo/", _to_board(views.undo_skip), name="undo_skip"),
    path("ask/", _to_board(views.ask), name="ask"),
    path("done/", _to_board(views.done), name="done"),
    path("done/signup/", _to_board(views.done_signup), name="done_signup"),
    path("done/share/", _to_board(views.done_share), name="done_share"),
    path("again/", _to_board(views.again), name="again"),
    # 上のどれにも当たらない古いURLも掲示板へ
    path("<path:rest>", views.to_board_any),
]
