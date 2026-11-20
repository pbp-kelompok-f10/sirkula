from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.marketplace.models import Product
from .api_serializers import BarterOfferCreateSerializer, BarterOfferSerializer, BarterTransactionSerializer, TrackingSerializer
from .models import BarterOffer, BarterTransaction
from .views import ACTIVE_OFFER_STATUSES


def participant_offers(user):
    return BarterOffer.objects.filter(Q(proposer=user) | Q(recipient=user))


def conflicting_offers(product_ids):
    return BarterOffer.objects.filter(status__in=ACTIVE_OFFER_STATUSES).filter(
        Q(requested_product_id__in=product_ids) | Q(offered_product_id__in=product_ids)
    )


class OfferListCreate(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        offers = participant_offers(request.user)
        direction = request.query_params.get('direction')
        if direction == 'incoming':
            offers = offers.filter(recipient=request.user)
        elif direction == 'outgoing':
            offers = offers.filter(proposer=request.user)
        return Response(BarterOfferSerializer(offers, many=True).data)

    def post(self, request):
        serializer = BarterOfferCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ids = [data['requested_product'], data['offered_product']]
        if ids[0] == ids[1]:
            return Response({'detail': 'Produk harus berbeda.'}, status=400)
        try:
            with transaction.atomic():
                products = {p.pk: p for p in Product.objects.select_for_update().filter(pk__in=ids).order_by('pk')}
                requested = products.get(ids[0])
                offered = products.get(ids[1])
                if not requested or not offered or any(not p.is_available or p.listing_type != Product.ListingType.BARTER for p in products.values()):
                    return Response({'detail': 'Produk barter tidak tersedia.'}, status=400)
                if requested.seller_id == request.user.pk or offered.seller_id != request.user.pk:
                    return Response({'detail': 'Kepemilikan produk tidak valid.'}, status=400)
                if conflicting_offers(ids).exists():
                    return Response({'detail': 'Produk sedang digunakan dalam barter aktif.'}, status=400)
                offer = BarterOffer.objects.create(proposer=request.user, recipient=requested.seller, requested_product=requested, offered_product=offered, message=data.get('message', ''))
        except IntegrityError:
            return Response({'detail': 'Tawaran sudah ada.'}, status=400)
        return Response(BarterOfferSerializer(offer).data, status=status.HTTP_201_CREATED)


class OfferDetail(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BarterOfferSerializer

    def get_queryset(self):
        return participant_offers(self.request.user)


class OfferAction(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, action):
        with transaction.atomic():
            offer = get_object_or_404(participant_offers(request.user).select_for_update(), pk=pk)
            if action in ('accept', 'reject', 'cancel'):
                authorized = offer.proposer_id == request.user.pk if action == 'cancel' else offer.recipient_id == request.user.pk
                if not authorized:
                    return Response({'detail': 'Tidak diizinkan.'}, status=403)
                if offer.status != BarterOffer.Status.PENDING:
                    return Response({'detail': 'Tawaran sudah diproses.'}, status=400)
                if action == 'accept':
                    ids = [offer.requested_product_id, offer.offered_product_id]
                    products = list(Product.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
                    if len(products) != 2 or not all(p.is_available for p in products) or conflicting_offers(ids).exclude(pk=offer.pk).exists():
                        return Response({'detail': 'Produk tidak tersedia untuk barter.'}, status=400)
                    offer.status = BarterOffer.Status.ACCEPTED
                    BarterTransaction.objects.create(offer=offer, proposer=offer.proposer, recipient=offer.recipient)
                    Product.objects.filter(pk__in=ids).update(is_available=False)
                else:
                    offer.status = BarterOffer.Status.REJECTED if action == 'reject' else BarterOffer.Status.CANCELLED
            elif action == 'shipping':
                if offer.status not in (BarterOffer.Status.ACCEPTED, BarterOffer.Status.SHIPPING):
                    return Response({'detail': 'Barter belum siap dikirim.'}, status=400)
                serializer = TrackingSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                field = 'proposer_tracking_number' if offer.proposer_id == request.user.pk else 'recipient_tracking_number'
                setattr(offer, field, serializer.validated_data['tracking_number'])
                if offer.proposer_tracking_number and offer.recipient_tracking_number:
                    offer.status = BarterOffer.Status.SHIPPING
            elif action == 'received':
                if offer.status != BarterOffer.Status.SHIPPING:
                    return Response({'detail': 'Barter belum dalam pengiriman.'}, status=400)
                field = 'proposer_received' if offer.proposer_id == request.user.pk else 'recipient_received'
                setattr(offer, field, True)
                if offer.proposer_received and offer.recipient_received:
                    offer.status = BarterOffer.Status.COMPLETED
                    BarterTransaction.objects.filter(offer=offer, completed_at__isnull=True).update(completed_at=timezone.now())
            else:
                return Response({'detail': 'Aksi tidak ditemukan.'}, status=404)
            offer.save()
        return Response(BarterOfferSerializer(offer).data)


class TransactionList(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BarterTransactionSerializer

    def get_queryset(self):
        return BarterTransaction.objects.filter(Q(proposer=self.request.user) | Q(recipient=self.request.user))


class TransactionDetail(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BarterTransactionSerializer

    def get_queryset(self):
        return BarterTransaction.objects.filter(Q(proposer=self.request.user) | Q(recipient=self.request.user))
