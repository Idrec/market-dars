from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # ===== DO'KON =====
    path('', views.home, name='home'),
    path('catalog/', views.product_list, name='product_list'),
    path('category/<slug:category_slug>/', views.product_list, name='category'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),

    # Savat
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),

    # Buyurtma va to'lov
    path('checkout/', views.checkout, name='checkout'),
    path('order/<int:order_id>/success/', views.order_success, name='order_success'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('payment/<int:order_id>/', views.payment, name='payment'),

    # Auth / profil
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='shop/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),

    # ===== ADMIN PANEL =====
    path('panel/', views.panel_dashboard, name='panel_dashboard'),
    path('panel/products/', views.panel_products, name='panel_products'),
    path('panel/products/add/', views.panel_product_form, name='panel_product_add'),
    path('panel/products/<int:pk>/edit/', views.panel_product_form, name='panel_product_edit'),
    path('panel/products/<int:pk>/delete/', views.panel_product_delete, name='panel_product_delete'),
    path('panel/images/<int:pk>/delete/', views.panel_image_delete, name='panel_image_delete'),
    path('panel/categories/', views.panel_categories, name='panel_categories'),
    path('panel/categories/<int:pk>/delete/', views.panel_category_delete, name='panel_category_delete'),
    path('panel/orders/', views.panel_orders, name='panel_orders'),
    path('panel/orders/<int:pk>/', views.panel_order_detail, name='panel_order_detail'),
]