from rest_framework import serializers
from .models import CustomUser, UserProfile
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from rest_framework import serializers
import logging


logger = logging.getLogger(__name__)

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    profile = serializers.DictField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ('email', 'password', 'first_name', 'last_name', 'role', 'profile')

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
        profile_data = validated_data.pop('profile', {})
        password = validated_data.pop('password')
        email = validated_data.get('email')

        logger.info(f"[Inscription] Tentative d’inscription de {email} avec rôle {validated_data.get('role')}")

        user = CustomUser.objects.create(**validated_data)
        user.set_password(password)
        user.save()

        UserProfile.objects.filter(user=user).update(**profile_data)

        logger.info(f"[Inscription] Utilisateur {email} créé avec succès")
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data['email']
        password = data['password']

        logger.info(f"[Connexion] Tentative de connexion pour {email}")
        user = authenticate(email=email, password=password)

        if user and user.is_active:
            refresh = RefreshToken.for_user(user)
            logger.info(f"[Connexion] Succès pour {email}")
            return {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': {
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': user.role,
                }
            }

        logger.warning(f"[Connexion] Échec pour {email}")
        raise serializers.ValidationError("Email ou mot de passe invalide")

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        exclude = ['id', 'user']

class UserWithProfileSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = ['email', 'first_name', 'last_name', 'role', 'profile']

class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['phone', 'address', 'allergies']  # adapte à tes champs

class UserUpdateSerializer(serializers.ModelSerializer):
    profile = UserProfileUpdateSerializer()

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'profile']

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})

        # Mise à jour des champs du CustomUser
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Mise à jour du profil lié
        profile = instance.profile
        for attr, value in profile_data.items():
            setattr(profile, attr, value)
        profile.save()

        return instance
