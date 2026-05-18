from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('cars/', views.car_list, name='car_list'),
    path('car/<int:car_id>/', views.car_detail, name='car_detail'),
    path('car/create/', views.car_create, name='car_create'),
    path('car/<int:car_id>/edit/', views.car_edit, name='car_edit'),
    path('car/<int:car_id>/delete/', views.car_delete, name='car_delete'),
    path('order/<int:order_id>/pdf/', views.order_pdf, name='order_pdf'),

    path('services/', views.service_list, name='service_list'),
    path('services/create/', views.service_create, name='service_create'),
    path('services/<int:service_id>/edit/', views.service_edit, name='service_edit'),
    path('services/<int:service_id>/delete/', views.service_delete, name='service_delete'),
    path('services/book/<int:service_id>/', views.book_service, name='book_service'),

    path('packages/', views.package_list, name='package_list'),
    path('packages/create/', views.package_create, name='package_create'),
    path('packages/<int:pk>/edit/', views.package_edit, name='package_edit'),
    path('packages/<int:pk>/delete/', views.package_delete, name='package_delete'),

    path('review/add/<int:car_id>/', views.add_review, name='add_review'),

    path('orders/', views.order_list, name='order_list'),
    path('order/create/<int:car_id>/', views.create_order, name='create_order'),

    path('favorites/', views.favorites, name='favorites'),
    path('favorite/toggle/<int:car_id>/', views.toggle_favorite, name='toggle_favorite'),

    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
]
