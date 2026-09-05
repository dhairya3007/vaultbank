from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Lockers
    path('lockers/', views.locker_list, name='locker_list'),
    path('lockers/add/', views.locker_add, name='locker_add'),
    path('lockers/<int:pk>/', views.locker_detail, name='locker_detail'),
    path('lockers/<int:pk>/edit/', views.locker_edit, name='locker_edit'),
    path('lockers/<int:pk>/delete/', views.locker_delete, name='locker_delete'),
    path('lockers/<int:pk>/add-user/', views.add_locker_user, name='add_locker_user'),
    path('lockers/<int:pk>/remove-user/<int:customer_pk>/', views.remove_locker_user, name='remove_locker_user'),

    # Customers
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.customer_add, name='customer_add'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('customers/<int:pk>/delete/', views.customer_delete, name='customer_delete'),

    # Scan & Check-in/out
    path('scan/', views.scan_token, name='scan_token'),
    path('scan/checkin/<int:pk>/', views.scan_checkin, name='scan_checkin'),
    path('checkin/', views.check_in, name='check_in'),
    path('checkout/<int:log_id>/', views.check_out, name='check_out'),
    path('checkout-all/<int:locker_id>/', views.check_out_all, name='check_out_all'),

    # Access Logs
    path('logs/', views.access_log, name='access_log'),

    # Reports
    path('reports/', views.report_dashboard_view, name='report_dashboard'),
    path('reports/generate/', views.report_generate_view, name='report_generate'),

    # API Explorer
    path('api-explorer/', views.api_explorer, name='api_explorer'),
]
