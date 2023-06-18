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
from django.contrib.auth import views as auth_views
from django.urls import path, include
from peddleconcept import views
from peddleconcept.views import riders

urlpatterns = [
    # Django admin site
    path('admin/', admin.site.urls),
    
    # admin login & password change views
    path('accounts/login/', views.MyLoginView.as_view(), name='login'),
    path('accounts/logout/', views.MyLogoutView.as_view(), name='logout'),
    # Password change - only usable if request.user.is_authenticated
    path('accounts/password_change/', auth_views.PasswordChangeView.as_view(), name='password_change'),
    path('accounts/password_change/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
    # Don't allow password resets in general - confusing for riders (without linked user account) vs admins
    #path("accounts/password_reset/", views.PasswordResetView.as_view(), name="password_reset"),
    #path("accounts/password_reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    #path("accounts/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    #path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),

    # Existing rider account verification
    path('accounts/login/code/<token>/', views.rider_token_login_migrate_view, name='token_login_old'),
    path('rider/migrate/code/<token>/', views.rider_token_login_migrate_view, name='token_login_migrate'),
    path('rider/existing/', views.rider_migrate_begin_view, name='rider_migrate_begin'), # basically rider_setup_begin
    path('rider/existing/verify', views.rider_migrate_verify_view, name='rider_migrate_verify'), # basically rider_setup_begin

    # Rider login
    path('rider/login/', views.rider_login_view, name='rider_login'),
    path('rider/login/verify/', views.rider_login_verify_view, name='rider_login_verify'),

    # New rider setup
    path('rider/invite/<token>/', views.rider_setup_invite_view, name='rider_setup_invite'),
    path('rider/setup/', riders.rider_setup_begin_view, name='rider_setup_begin'),
    path('rider/setup/verify', riders.rider_setup_verify_view, name='rider_setup_verify'),
    path('rider/setup/profile', riders.rider_setup_final_view, name='rider_setup_final'),

    # Profile views
    path('profile/', riders.rider_profile_view, name='my_profile'),
    path('profile/edit/', riders.rider_profile_edit_view, name='rider_edit_profile'),
    path('profile/payroll/', riders.rider_profile_edit_payroll_view, name='rider_edit_payroll'),
    path('profile/verify/', riders.rider_profile_verify_email_view, name='rider_profile_verify_email'),

    path('', views.index_view, name='index'),
    path('contacts/', views.rider_list_view, name='rider_list'),

    # Tour schedules
    path('tours/', views.schedules_view),
    path('tours/schedule/', views.schedules_view),
    path('tours/schedule/<tours_date>/', views.schedules_view),
    path('tours/area/<tour_area_id>/', views.schedules_view, name='tours_today'),
    path('tours/area/<tour_area_id>/<tours_date>/', views.schedules_view, name='tours_for'),
    
    # Tour dashboard
    path('tours/dashboard/', views.schedules_dashboard_view, name='tour_dashboard'),
    path('tours/dashboard/data/', views.schedules_dashboard_data_view, name='tour_dashboard_data'),
    
    # Rider tour schedules
    path('tours/rider/', views.rider_schedules_view, name='tours_rider_today'),
    path('tours/rider/<tours_date>/', views.rider_schedules_view, name='tours_rider'),
    path('tours/data/rider/', views.rider_tours_data_view, name='tours_rider_data'),

    path('tours/update/', views.update_tours_data, name='update_tours'),
    path('tours/data/', views.tours_data_view, name='tour_sched_data'),
    path('tours/edit-area/<tour_area_id>/<tours_date>/', views.schedule_editor_view, name='tour_sched_edit'),
    path('tours/roster-area/<tour_area_id>/<tours_date>/', views.roster_admin_view, name='tour_roster_admin'),
    path('tours/data/editor/', views.schedule_admin_data_view, name='tour_sched_admin_data'),
    path('tours/reports/week/<week_start>/', views.tour_pays_view, name='tour_pays'),
    path('tours/reports/data/', views.tour_pays_data_view, name='tour_pays_data'),
    path('tours/venues/week/<week_start>/', views.venues_report_view, name='venues_report'),
    path('tours/venues/data/', views.venues_report_data_view, name='venues_report_data'),
]
