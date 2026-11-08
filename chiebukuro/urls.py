from django.urls import path
from django.views.generic import RedirectView

from . import views


app_name = "chiebukuro"

urlpatterns = [
    path("", views.home, name="home"),
    # つぶやき
    path("posts/", views.post_list, name="posts"),
    path("post/", views.post_new, name="post_new"),
    path("p/<int:pk>/", views.post_detail, name="post"),
    path("p/<int:pk>/delete/", views.delete_post, name="delete_post"),
    # 質問
    path("questions/", views.question_index, name="questions"),
    path("ask/", views.ask, name="ask"),
    path("q/<int:pk>/", views.question_detail, name="question"),
    path("q/<int:pk>/interest/", views.toggle_interest, name="interest"),
    path("a/<int:pk>/thanks/", views.toggle_thanks, name="thanks"),
    path("a/<int:pk>/delete/", views.delete_answer, name="delete_answer"),
    # ゆずりあい
    path("items/", views.item_list, name="items"),
    path("items/new/", views.item_new, name="item_new"),
    path("items/<int:pk>/", views.item_detail, name="item"),
    path("items/<int:pk>/state/", views.item_state, name="item_state"),
    path("items/<int:pk>/request/", views.item_request, name="item_request"),
    path("give/", RedirectView.as_view(url="/swiss-board/items/?kind=give", permanent=False)),
    path("books/", RedirectView.as_view(url="/swiss-board/items/?kind=lend&genre=books", permanent=False)),
    # 募集・告知
    path("notices/", views.notice_list, name="notices"),
    path("notices/new/", views.notice_new, name="notice_new"),
    path("notices/<int:pk>/", views.notice_detail, name="notice"),
    path("notices/<int:pk>/request/", views.notice_request, name="notice_request"),
    path("notices/<int:pk>/withdraw/", views.notice_withdraw, name="notice_withdraw"),
    # 2人だけのやりとり
    path("talk/<int:pk>/", views.talk, name="talk"),
    path("talk/<int:pk>/choose/", views.talk_choose, name="talk_choose"),
    # 自分・ほかの人
    path("notifications/", views.notifications, name="notifications"),
    path("me/", views.my_page, name="me"),
    path("me/profile/", views.profile_edit, name="profile_edit"),
    path("avatar.svg", views.avatar_preview, name="avatar_preview"),
    path("u/<str:username>/", views.profile, name="profile"),
    path("new/", views.new_choice, name="new"),
    path("edit/<str:kind>/<int:pk>/", views.edit_mine, name="edit"),
    path("delete/<str:kind>/<int:pk>/", views.delete_mine, name="delete"),
    path("search/", views.search, name="search"),
    path("report/", views.report, name="report"),
    path("rules/", views.rules, name="rules"),
    path("install/", views.install_guide, name="install"),
    path("rules/agree/", views.rules_agree, name="rules_agree"),
    path("stamp/", views.stamp, name="stamp"),
    # HOME: アンケート・広告
    path("today/", views.today_strip, name="today"),
    path("fx/", views.fx_detail, name="fx"),
    path("daily/off/", views.daily_off, name="daily_off"),
    path("polls/", views.poll_list, name="polls"),
    path("polls/<int:pk>/vote/", views.poll_vote, name="poll_vote"),
    path("ad/<int:pk>/", views.sponsor_click, name="sponsor"),
    # 設定・プッシュ通知
    path("me/settings/", views.settings_view, name="settings"),
    path("me/<str:section>/", views.my_list, name="my_list"),
    path("push/subscribe/", views.push_subscribe, name="push_subscribe"),
    path("push/unsubscribe/", views.push_unsubscribe, name="push_unsubscribe"),
    path("push/test/", views.push_test, name="push_test"),
]
