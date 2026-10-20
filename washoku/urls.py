from django.urls import path

from . import views


app_name = "washoku"

urlpatterns = [
    path("", views.home, name="home"),
]
