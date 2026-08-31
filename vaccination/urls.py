from django.urls import path

from . import views


app_name = "vaccination"


urlpatterns = [
    path(
        "",
        views.home,
        name="home",
    ),

    path(
        "children/",
        views.children,
        name="children",
    ),

    path(
        "children/add/",
        views.child_create,
        name="child_create",
    ),

    path(
        "children/<int:pk>/edit/",
        views.child_edit,
        name="child_edit",
    ),

    path(
        "children/<int:pk>/switch/",
        views.child_switch,
        name="child_switch",
    ),
    

    path(
        "records/",
        views.records,
        name="records",
    ),

    path(
        "records/add/",
        views.record_create,
        name="record_create",
    ),
    
    path(
        "records/<int:pk>/edit/",
        views.record_edit,
        name="record_edit",
    ),

    path(
        "records/<int:pk>/delete/",
        views.record_delete,
        name="record_delete",
    ),

    path(
        "records/<int:pk>/",
        views.record_detail,
        name="record_detail",
    ),

    path(
        "components/<int:pk>/",
        views.component_detail,
        name="component_detail",
    ),

    path(
        "schedule/",
        views.schedule,
        name="schedule",
    ),

    path(
        "doctor/",
        views.doctor,
        name="doctor",
    ),

    path(
        "settings/",
        views.settings_view,
        name="settings",
    ),

    path(
        "collaborators/",
        views.collaborators,
        name="collaborators",
    ),

    path(
        "collaborators/<int:pk>/permission/",
        views.collaborator_permission_update,
        name="collaborator_permission_update",
    ),

    path(
        "collaborators/<int:pk>/remove/",
        views.collaborator_remove,
        name="collaborator_remove",
    ),
]