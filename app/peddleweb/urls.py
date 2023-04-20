"""peddleweb URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from peddleconcept import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('accounts/', include('django.contrib.auth.urls')),

    path('', views.index_view, name='index'),
    path('profile/', views.homepage_view, name='home'),
    path('contacts/', views.rider_list_view, name='rider_list'),
    path('tours/', views.schedules_view),
    path('tours/schedule/', views.schedules_view, name='tours_today'),
    path('tours/dashboard/', views.schedules_dashboard_view, name='tour_dashboard'),
    path('tours/dashboard/data/', views.schedules_dashboard_data_view, name='tour_dashboard_data'),
    path('tours/schedule/<tours_date>/', views.schedules_view, name='tours_for'),
    path('tours/rider/', views.rider_schedules_view, name='tours_rider_today'),
    path('tours/rider/<tours_date>/', views.rider_schedules_view, name='tours_rider'),

    path('tours/update/', views.update_tours_data, name='update_tours'),
    path('tours/data/', views.tours_data_view, name='tour_sched_data'),
    path('tours/edit/<tours_date>/', views.schedule_editor_view, name='tour_sched_edit'),
    path('tours/reports/week/<week_start>/', views.tour_pays_view, name='tour_pays'),
    path('tours/reports/data/', views.tour_pays_data_view, name='tour_pays_data'),
    path('tours/venues/week/<week_start>/', views.venues_report_view, name='venues_report'),
    path('tours/venues/data/', views.venues_report_data_view, name='venues_report_data'),
]
