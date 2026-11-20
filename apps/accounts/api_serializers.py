from django.contrib.auth import authenticate, get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .forms import MAX_AVATAR_BYTES, generate_internal_username
from .models import Profile

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(min_length=2, max_length=120)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    location = serializers.CharField(max_length=80, required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email ini sudah terdaftar.")
        return value

    def validate(self, attrs):
        user = User(
            username=generate_internal_username(attrs['full_name']),
            first_name=attrs['full_name'],
            email=attrs['email'],
        )
        try:
            password_validation.validate_password(attrs['password'], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': list(exc.messages)})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        full_name = validated_data['full_name']
        user = User.objects.create_user(
            username=generate_internal_username(full_name),
            first_name=full_name,
            email=validated_data['email'],
            password=validated_data['password'],
        )
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.display_name = full_name
        profile.full_name = full_name
        profile.location = validated_data.get('location', '')
        profile.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = User.objects.filter(email__iexact=attrs['email'].strip()).order_by('pk').first()
        authenticated = authenticate(
            request=self.context.get('request'),
            username=user.get_username() if user else '',
            password=attrs['password'],
        )
        if not authenticated or not authenticated.is_active:
            raise serializers.ValidationError('Email atau password salah.')
        attrs['user'] = authenticated
        return attrs


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Profile
        fields = [
            'username', 'email', 'display_name', 'full_name', 'bio', 'location',
            'avatar', 'reputation_score', 'item_quality_score',
            'successful_transactions', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'reputation_score', 'item_quality_score', 'successful_transactions',
            'created_at', 'updated_at',
        ]

    def validate_avatar(self, value):
        if value and value.size > MAX_AVATAR_BYTES:
            raise serializers.ValidationError('Ukuran foto maksimal 2 MB.')
        return value

    def update(self, instance, validated_data):
        old_avatar = instance.avatar.name if instance.avatar else None
        instance = super().update(instance, validated_data)
        if old_avatar and old_avatar != (instance.avatar.name if instance.avatar else None):
            instance.avatar.storage.delete(old_avatar)
        return instance
