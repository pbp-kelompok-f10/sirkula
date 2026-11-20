from rest_framework import serializers

from .models import BarterOffer, BarterTransaction


class BarterOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = BarterOffer
        fields = '__all__'


class BarterOfferCreateSerializer(serializers.Serializer):
    requested_product = serializers.IntegerField(min_value=1)
    offered_product = serializers.IntegerField(min_value=1)
    message = serializers.CharField(required=False, allow_blank=True)


class TrackingSerializer(serializers.Serializer):
    tracking_number = serializers.CharField(max_length=100, trim_whitespace=True)


class BarterTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BarterTransaction
        fields = '__all__'
