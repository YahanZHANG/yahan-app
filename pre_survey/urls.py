from django.urls import path

from . import views


app_name = "pre_survey"

urlpatterns = [
    path("", views.start, name="start"),
    path("nickname/", views.nickname, name="nickname"),
    path("themes/", views.themes, name="themes"),
    path("q/", views.question, name="question"),
    path("q/<int:pk>/", views.question_action, name="question_action"),
    path("q/<int:pk>/undo/", views.undo_skip, name="undo_skip"),
    path("ask/", views.ask, name="ask"),
    path("done/", views.done, name="done"),
    path("done/signup/", views.done_signup, name="done_signup"),
    path("again/", views.again, name="again"),
]
