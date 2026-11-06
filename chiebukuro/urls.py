from django.urls import path

from . import views


app_name = "chiebukuro"

urlpatterns = [
    path("", views.home, name="home"),
    path("ask/", views.ask, name="ask"),
    path("q/<int:pk>/", views.question_detail, name="question"),
    path("q/<int:pk>/interest/", views.toggle_interest, name="interest"),
    path("a/<int:pk>/thanks/", views.toggle_thanks, name="thanks"),
    path("a/<int:pk>/delete/", views.delete_answer, name="delete_answer"),
    path("give/", views.item_list, {"kind": "give"}, name="give"),
    path("books/", views.item_list, {"kind": "book"}, name="books"),
    path("items/new/<str:kind>/", views.item_new, name="item_new"),
    path("items/<int:pk>/", views.item_detail, name="item"),
    path("items/<int:pk>/state/", views.item_state, name="item_state"),
    path("items/<int:pk>/request/", views.item_request, name="item_request"),
    path("talk/<int:pk>/", views.talk, name="talk"),
    path("talk/<int:pk>/choose/", views.talk_choose, name="talk_choose"),
    path("me/", views.my_page, name="me"),
    path("report/", views.report, name="report"),
]
