from django.urls import path
from . import api_views_drf as views

app_name = 'transactions_api'
urlpatterns = [
    path('cart/', views.CartView.as_view(), name='cart'),
    path('cart/items/<int:product_id>/', views.CartItemView.as_view(), name='cart-item'),
    path('checkout/', views.CheckoutView.as_view(), name='checkout'),
    path('orders/', views.OrderList.as_view(), name='orders'),
    path('orders/<int:pk>/', views.OrderDetail.as_view(), name='order-detail'),
    path('orders/<int:pk>/status/', views.OrderStatusView.as_view(), name='order-status'),
    path('orders/<int:pk>/payment-status/', views.PaymentStatusView.as_view(), name='payment-status'),
    path('notifications/', views.NotificationList.as_view(), name='notifications'),
    path('notifications/<int:pk>/read/', views.NotificationRead.as_view(), name='notification-read'),
]
