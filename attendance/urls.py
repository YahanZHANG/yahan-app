from django.urls import path
from . import views

app_name = 'attendance'
urlpatterns = [
    path('login/', views.sign_in, name='login'),
    path('verify/', views.verify, name='verify'),
    path('logout/', views.sign_out, name='logout'),
    path('', views.index, name='index'),
    path('people/', views.people, name='people'),
    path('people/add/', views.add_person, name='add_person'),
    path('people/<int:pk>/payment/', views.add_payment, name='add_payment'),
    path('people/<int:pk>/toggle/', views.toggle_person, name='toggle_person'),
    path('people/<int:pk>/children/add/', views.add_child, name='add_child'),
    path('children/<int:pk>/edit/', views.edit_child, name='edit_child'),
    path('schedule/', views.schedule, name='schedule'),
    path('committees/', views.committees, name='committees'),
    path('committees/add/', views.add_committee, name='add_committee'),
    path('history/', views.history, name='history'),
    path('export.xlsx', views.export_excel, name='excel'),
    path('export.pdf', views.export_pdf, name='pdf'),
]
