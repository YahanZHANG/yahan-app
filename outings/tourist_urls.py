
from django.urls import path

from . import find_views, tourist_views


urlpatterns = [
    path(
        "",
        find_views.from_trips,
        name="tourist_spot_list",
    ),
    path(
        "<int:pk>/",
        tourist_views.tourist_spot_detail,
        name="tourist_spot_detail",
    ),

    path(
        "<int:pk>/heart/",
        tourist_views.toggle_tourist_heart,
        name="toggle_tourist_heart",
    ),
]
