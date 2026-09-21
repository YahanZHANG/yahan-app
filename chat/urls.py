from django.urls import path

from . import views


app_name = "chat"


urlpatterns = [

    # チャット一覧

    path(
        "",
        views.chat_list,
        name="list",
    ),

    # IDで友達を検索

    path(
        "add/",
        views.chat_add,
        name="add",
    ),

    # 友達申請

    path(
        "request/<int:user_id>/",
        views.friend_request,
        name="friend_request",
    ),

    # 承認・拒否

    path(
        "decision/<int:connection_id>/",
        views.friend_decision,
        name="friend_decision",
    ),

    # ピン留め

    path(
        "pin/<int:user_id>/",
        views.chat_pin,
        name="pin",
    ),

    # 個別チャット

    path(
        "<int:user_id>/",
        views.chat_room,
        name="room",
    ),

]