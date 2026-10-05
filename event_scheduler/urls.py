from django.urls import path

from . import views


app_name = "event_scheduler"


urlpatterns = [

    path(
        "",
        views.event_list,
        name="event_list",
    ),

    path(
        "create/",
        views.event_create,
        name="event_create",
    ),

    path(
        "<int:event_id>/",
        views.event_detail,
        name="event_detail",
    ),

    path(
        "<int:event_id>/dates/add/",
        views.event_date_add,
        name="event_date_add",
    ),

    path(
        "<int:event_id>/join/",
        views.join_event,
        name="join_event",
    ),

    path(
        "<int:event_id>/leave/",
        views.leave_event,
        name="leave_event",
    ),


    path(
        "<int:event_id>/respond/",
        views.event_respond,
        name="event_respond",
    ),

    path(
        "<int:event_id>/admins/",
        views.event_admins,
        name="event_admins",
    ),

    path(
        "<int:event_id>/admins/invite/",
        views.event_admin_invite,
        name="event_admin_invite",
    ),

    path(
        "admin-invitations/<int:invitation_id>/accept/",
        views.event_admin_invitation_accept,
        name="event_admin_invitation_accept",
    ),

    path(
        "admin-invitations/<int:invitation_id>/decline/",
        views.event_admin_invitation_decline,
        name="event_admin_invitation_decline",
    ),

    path(
        "archived/",
        views.archived_event_list,
        name="archived_event_list",
    ),

    path(
        "<int:event_id>/admins/invitations/<int:invitation_id>/cancel/",
        views.event_admin_invitation_cancel,
        name="event_admin_invitation_cancel",
    ),

    path(
        "<int:event_id>/admins/<int:admin_id>/remove/",
        views.event_admin_remove,
        name="event_admin_remove",
    ),

    path(
        "<int:event_id>/admins/leave/",
        views.event_admin_leave,
        name="event_admin_leave",
    ),

    path(
        "<int:event_id>/archive/",
        views.event_archive,
        name="event_archive",
    ),

    path(
        "<int:event_id>/restore/",
        views.event_restore,
        name="event_restore",
    ),

    path(
        "<int:event_id>/delete/",
        views.event_delete,
        name="event_delete",
    ),

]