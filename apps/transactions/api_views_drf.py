from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.marketplace.models import Product
from .api_serializers import CartProductSerializer, CheckoutSerializer, NotificationSerializer, OrderSerializer, OrderStatusSerializer
from .cart import Cart
from .midtrans import create_qris_payment, get_payment_status, get_qr_code_url
from .models import Order, OrderItem, OrderStatusHistory, TransactionNotification
from .views import SHIPPING_COSTS, apply_payment_status


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = Cart(request).get_items()
        return Response({'items': CartProductSerializer(items, many=True).data, 'total': str(sum((p.price for p in items), Decimal('0')))})

    def delete(self, request):
        Cart(request).clear()
        return Response(status=204)


class CartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)
        if not product.is_available or product.listing_type != Product.ListingType.THRIFT:
            return Response({'detail': 'Produk tidak tersedia untuk dibeli.'}, status=400)
        Cart(request).add(product)
        return Response(status=204)

    def delete(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)
        Cart(request).remove(product)
        return Response(status=204)


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        cart = Cart(request)
        items = cart.get_items()
        if not items:
            return Response({'detail': 'Keranjang kosong.'}, status=400)
        with transaction.atomic():
            locked = list(Product.objects.select_for_update().filter(pk__in=[p.pk for p in items], is_available=True, listing_type=Product.ListingType.THRIFT).order_by('pk'))
            if len(locked) != len(items):
                return Response({'detail': 'Produk tidak tersedia.'}, status=400)
            subtotal = sum((p.price for p in locked), Decimal('0'))
            shipping_cost = SHIPPING_COSTS[data['shipping_method']]
            order = Order.objects.create(buyer=request.user, address=data['address'], phone_number=data['phone_number'], purchase_method=data['purchase_method'], shipping_method=data['shipping_method'], shipping_cost=shipping_cost, admin_fee=Decimal('1000'), subtotal=subtotal, total=subtotal + shipping_cost + Decimal('1000'))
            OrderItem.objects.bulk_create([OrderItem(order=order, product=p, price=p.price) for p in locked])
            Product.objects.filter(pk__in=[p.pk for p in locked]).update(is_available=False)
            OrderStatusHistory.objects.create(order=order, status=Order.Status.PENDING, note='Pesanan dibuat.')
        try:
            payment = create_qris_payment(order, list(order.items.select_related('product')))
            qr_url = get_qr_code_url(payment)
            if not qr_url:
                raise ValueError('Midtrans tidak mengembalikan URL QRIS.')
            order.payment_transaction_id = payment.get('transaction_id', '')
            order.payment_qr_url = qr_url
            order.save(update_fields=['payment_transaction_id', 'payment_qr_url'])
        except Exception:
            with transaction.atomic():
                Product.objects.filter(order_items__order=order).update(is_available=True)
                order.delete()
            return Response({'detail': 'QRIS belum dapat dibuat.'}, status=502)
        cart.clear()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


def accessible_orders(user):
    return Order.objects.filter(Q(buyer=user) | Q(items__product__seller=user)).distinct()


class OrderList(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        queryset = accessible_orders(self.request.user)
        role = self.request.query_params.get('role')
        if role == 'buyer':
            queryset = queryset.filter(buyer=self.request.user)
        elif role == 'seller':
            queryset = queryset.filter(items__product__seller=self.request.user)
        order_status = self.request.query_params.get('status')
        if order_status in Order.Status.values:
            queryset = queryset.filter(status=order_status)
        return queryset.prefetch_related('items', 'status_history')


class OrderDetail(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return accessible_orders(self.request.user).prefetch_related('items', 'status_history')


class OrderStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = OrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            order = get_object_or_404(Order.objects.select_for_update(), pk=pk)
            if not order.items.filter(product__seller=request.user).exists():
                return Response({'detail': 'Hanya penjual dapat mengubah status.'}, status=403)
            transitions = {Order.Status.PENDING: {Order.Status.CONFIRMED, Order.Status.CANCELLED}, Order.Status.CONFIRMED: {Order.Status.SHIPPED, Order.Status.CANCELLED}, Order.Status.SHIPPED: {Order.Status.COMPLETED}}
            next_status = serializer.validated_data['status']
            if next_status not in transitions.get(order.status, set()):
                return Response({'detail': 'Perubahan status tidak valid.'}, status=400)
            order.status = next_status
            order.save(update_fields=['status', 'updated_at'])
            OrderStatusHistory.objects.create(order=order, status=next_status, note=f'Status diubah menjadi {order.get_status_display()}.')
            if order.buyer_id:
                TransactionNotification.objects.create(recipient=order.buyer, order=order, message=f'Status order {order.order_number} berubah menjadi {order.get_status_display()}.')
        return Response(OrderSerializer(order).data)


class PaymentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk, buyer=request.user)
        try:
            payment = get_payment_status(order.order_number)
            apply_payment_status(order, payment)
        except Exception:
            return Response({'detail': 'Status pembayaran belum dapat diperiksa.'}, status=502)
        return Response(OrderSerializer(order).data)


class NotificationList(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return TransactionNotification.objects.filter(recipient=self.request.user).order_by('-created_at')


class NotificationRead(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        notification = get_object_or_404(TransactionNotification, pk=pk, recipient=request.user)
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)
