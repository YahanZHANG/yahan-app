from django.urls import path

from . import views


app_name = "colorcheck"


urlpatterns = [
    path("", views.index, name="index"),
]