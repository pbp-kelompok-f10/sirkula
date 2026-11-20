from rest_framework import serializers

from apps.marketplace.models import Product
from .models import Order, OrderItem, OrderStatusHistory, TransactionNotification
from .views import SHIPPING_COSTS


class CartProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'seller']
        read_only_fields = fields


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'price']
        read_only_fields = fields


class OrderHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusHistory
        fields = ['id', 'status', 'note', 'created_at']
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = '__all__'


class CheckoutSerializer(serializers.Serializer):
    address = serializers.CharField(max_length=255)
    phone_number = serializers.CharField(max_length=30)
    purchase_method = serializers.ChoiceField(choices=Order.PurchaseMethod.choices, default=Order.PurchaseMethod.COD)
    shipping_method = serializers.ChoiceField(choices=list(SHIPPING_COSTS), default='REGULAR')


class OrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionNotification
        fields = ['id', 'order', 'message', 'is_read', 'created_at']
        read_only_fields = fields
