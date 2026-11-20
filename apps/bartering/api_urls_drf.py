from django.urls import path
from . import api_views_drf as views

app_name = 'bartering_api'
urlpatterns = [
    path('offers/', views.OfferListCreate.as_view(), name='offers'),
    path('offers/<int:pk>/', views.OfferDetail.as_view(), name='offer-detail'),
    path('offers/<int:pk>/<str:action>/', views.OfferAction.as_view(), name='offer-action'),
    path('transactions/', views.TransactionList.as_view(), name='transactions'),
    path('transactions/<int:pk>/', views.TransactionDetail.as_view(), name='transaction-detail'),
]
