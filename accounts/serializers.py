from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
import logging

from restaurants.models import Restaurant
from .models import CustomUser, UserProfile

logger = logging.getLogger(__name__)

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    profile = serializers.DictField(write_only=True, required=False)
    restaurant_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = CustomUser
        fields = ('email', 'password', 'first_name', 'last_name', 'role', 'profile', 'restaurant_id')

    def validate_email(self, value):
        try:
            validate_email(value)
        except DjangoValidationError:
            raise serializers.ValidationError("Email invalide")
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Cet email est déjà utilisé")
        return value

    def validate_role(self, value):
        valid_roles = ['CLIENT', 'FOURNISSEUR', 'RESTAURATEUR']
        if value not in valid_roles:
            raise serializers.ValidationError(f"Rôle invalide. Doit être l’un de {valid_roles}")
        return value

    def create(self, validated_data):
        profile_data = validated_data.pop('profile', {}) or {}
        restaurant_id = validated_data.pop('restaurant_id', None)
        password = validated_data.pop('password')

        user = CustomUser.objects.create(**validated_data)
        user.set_password(password)
        user.save()

        # Assure-toi qu’un UserProfile existe (get_or_create)
        UserProfile.objects.get_or_create(user=user, defaults=profile_data)
        if profile_data:
            # Si déjà créé, on met à jour
            UserProfile.objects.filter(user=user).update(**profile_data)

        # Associer le restaurateur comme owner d'un restaurant si fourni
        if user.role == 'RESTAURATEUR' and restaurant_id:
            try:
                restaurant = Restaurant.objects.get(id=restaurant_id)
                restaurant.owner = user
                restaurant.save()
            except Restaurant.DoesNotExist:
                raise serializers.ValidationError("Restaurant non trouvé.")

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data["email"]
        password = data["password"]

        logger.info(f"[Connexion] Tentative de connexion pour {email}")
        user = authenticate(self.context.get("request"), email=email, password=password)  # ← IMPORTANT

        if user and user.is_active:
            refresh = RefreshToken.for_user(user)
            logger.info(f"[Connexion] Succès pour {email}")
            return {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": {
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                },
            }

        logger.warning(f"[Connexion] Échec pour {email}")
        raise serializers.ValidationError("Email ou mot de passe invalide")

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        exclude = ['id', 'user']


class RestaurantLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = ["id", "name", "city"]


class UserWithProfileSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    # ✅ Ne PAS mettre source="restaurants" (AssertionError sinon)
    restaurants = RestaurantLiteSerializer(many=True, read_only=True)
    active_restaurant_id = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            'email', 'first_name', 'last_name', 'role', 'profile',
            'restaurants', 'active_restaurant_id'
        ]

    def get_active_restaurant_id(self, obj):
        first = obj.restaurants.first()
        return first.id if first else None


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['phone', 'address', 'allergies']


class UserUpdateSerializer(serializers.ModelSerializer):
    profile = UserProfileUpdateSerializer()

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'profile']

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        profile, _ = UserProfile.objects.get_or_create(user=instance)
        for attr, value in profile_data.items():
            setattr(profile, attr, value)
        profile.save()

        return instance

