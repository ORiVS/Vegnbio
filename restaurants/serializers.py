from datetime import datetime
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import serializers

from .models import (
    Restaurant, Room, Reservation, Evenement,
    EvenementRegistration, EventInvite, RestaurantClosure
)

User = get_user_model()


# --- ROOMS ---
class RoomReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ['id', 'name', 'capacity']


class RoomWriteSerializer(serializers.ModelSerializer):
    restaurant = serializers.PrimaryKeyRelatedField(queryset=Restaurant.objects.all())

    class Meta:
        model = Room
        fields = ['id', 'restaurant', 'name', 'capacity']


# --- RESTAURANT ---
class RestaurantSerializer(serializers.ModelSerializer):
    rooms = RoomReadSerializer(many=True, read_only=True)

    class Meta:
        model = Restaurant
        fields = [
            'id', 'name', 'address', 'city', 'postal_code',
            'capacity', 'wifi_available', 'printer_available',
            'member_trays_available', 'delivery_trays_available',
            'animations_enabled', 'animation_day',
            'opening_time_mon_to_thu', 'closing_time_mon_to_thu',
            'opening_time_friday', 'closing_time_friday',
            'opening_time_saturday', 'closing_time_saturday',
            'opening_time_sunday', 'closing_time_sunday',
            'rooms'
        ]


class RestaurantUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = [
            'name', 'address', 'city', 'postal_code',
            'capacity', 'wifi_available', 'printer_available',
            'member_trays_available', 'delivery_trays_available',
            'animations_enabled', 'animation_day',
            'opening_time_mon_to_thu', 'closing_time_mon_to_thu',
            'opening_time_friday', 'closing_time_friday',
            'opening_time_saturday', 'closing_time_saturday',
            'opening_time_sunday', 'closing_time_sunday',
        ]


# --- RESERVATION ---
class ReservationSerializer(serializers.ModelSerializer):
    customer = serializers.HiddenField(default=serializers.CurrentUserDefault())
    customer_email = serializers.EmailField(write_only=True, required=False)

    customer_email_read = serializers.EmailField(source='customer.email', read_only=True)
    customer_first_name = serializers.CharField(source='customer.first_name', read_only=True)
    customer_last_name = serializers.CharField(source='customer.last_name', read_only=True)
    customer_id_read = serializers.IntegerField(source='customer.id', read_only=True)

    room_name = serializers.SerializerMethodField()
    restaurant_name = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Reservation
        fields = [
            'id',
            'customer', 'customer_email',
            'customer_email_read', 'customer_first_name', 'customer_last_name', 'customer_id_read',
            'restaurant', 'restaurant_name',
            'date', 'start_time', 'end_time',
            'party_size',
            'room', 'room_name', 'full_restaurant',
            'status', 'created_at'
        ]
        read_only_fields = [
            'created_at', 'room', 'room_name', 'full_restaurant', 'status',
            'customer_email_read', 'customer_first_name', 'customer_last_name', 'customer_id_read'
        ]

    def get_room_name(self, obj):
        return obj.room.name if obj.room else None

    def get_restaurant_name(self, obj):
        return obj.restaurant.name if obj.restaurant else None

    def validate(self, data):
        restaurant = data.get('restaurant')
        date_ = data.get('date')
        start = data.get('start_time')
        end = data.get('end_time')
        party_size = data.get('party_size')

        if not restaurant:
            raise serializers.ValidationError("Le restaurant est requis.")
        if not party_size or party_size <= 0:
            raise serializers.ValidationError("party_size (nombre de places) doit être > 0.")

        today = timezone.localdate()
        now_t = timezone.localtime().time()
        if date_ < today:
            raise serializers.ValidationError("Impossible de réserver dans le passé.")
        if date_ == today and end <= now_t:
            raise serializers.ValidationError("Le créneau est déjà passé aujourd'hui.")
        if start >= end:
            raise serializers.ValidationError("L'heure de début doit être avant l'heure de fin.")

        if not restaurant.is_time_range_within_opening(date_, start, end):
            raise serializers.ValidationError("Créneau hors horaires d'ouverture du restaurant.")

        ev_qs = Evenement.objects.filter(
            restaurant=restaurant,
            date=date_,
            is_blocking=True,
            status__in=["PUBLISHED", "FULL"],
            start_time__lt=end,
            end_time__gt=start
        )
        if ev_qs.exists():
            raise serializers.ValidationError("Créneau indisponible (événement bloquant).")

        from .models import Reservation as Res
        conflicts_full = Res.objects.filter(
            restaurant=restaurant, date=date_,
            start_time__lt=end, end_time__gt=start,
            full_restaurant=True
        )
        if self.instance:
            conflicts_full = conflicts_full.exclude(pk=self.instance.pk)
        if conflicts_full.exists():
            raise serializers.ValidationError("Le restaurant est déjà réservé en entier sur ce créneau.")

        return data

    def create(self, validated):
        request = self.context.get('request')
        email = (validated.pop('customer_email', None) or "").strip()

        if request and getattr(request.user, 'role', None) == 'RESTAURATEUR':
            validated.pop('customer', None)
            if not email:
                raise serializers.ValidationError("customer_email est requis (création par restaurateur).")
            try:
                customer = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                raise serializers.ValidationError("Client introuvable pour ce customer_email.")
            validated['customer'] = customer
            return super().create(validated)

        return super().create(validated)


# --- EVENEMENTS ---
class EvenementSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    current_registrations = serializers.IntegerField(source='registrations.count', read_only=True)
    published_at = serializers.DateTimeField(read_only=True)
    full_at = serializers.DateTimeField(read_only=True)
    cancelled_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Evenement
        fields = [
            'id','restaurant','restaurant_name',
            'title','description','type',
            'date','start_time','end_time',
            'capacity','current_registrations',
            'is_public','status',
            'is_blocking','room','rrule',
            'published_at','full_at','cancelled_at',
            'created_at','updated_at',
            'requires_supplier_confirmation','supplier_deadline_days'
        ]
        read_only_fields = [
            'status','current_registrations',
            'published_at','full_at','cancelled_at',
            'created_at','updated_at'
        ]

    def validate(self, data):
        instance = getattr(self, 'instance', None)
        restaurant = data.get('restaurant') or (instance.restaurant if instance else None)
        date_ = data.get('date') or (instance.date if instance else None)
        start = data.get('start_time') or (instance.start_time if instance else None)
        end = data.get('end_time') or (instance.end_time if instance else None)
        is_blocking = data.get('is_blocking') if 'is_blocking' in data else (instance.is_blocking if instance else None)
        room = data.get('room') if 'room' in data else (instance.room if instance else None)

        if not (restaurant and date_ and start and end):
            return data

        if start >= end:
            raise serializers.ValidationError("start_time doit être avant end_time.")

        today = timezone.localdate()
        now_t = timezone.localtime().time()
        if date_ < today:
            raise serializers.ValidationError("Impossible de créer/éditer un évènement dans le passé.")
        if date_ == today and end <= now_t:
            raise serializers.ValidationError("L’horaire est déjà passé pour aujourd’hui.")

        if not restaurant.is_time_range_within_opening(date_, start, end):
            raise serializers.ValidationError("Créneau hors horaires d'ouverture du restaurant.")

        if instance and ('capacity' in data) and (data['capacity'] is not None):
            if data['capacity'] < instance.registrations.count():
                raise serializers.ValidationError("La capacité ne peut pas être inférieure au nombre d’inscrits actuel.")

        if is_blocking:
            ev_qs = Evenement.objects.filter(
                restaurant=restaurant,
                date=date_,
                is_blocking=True,
                status__in=["PUBLISHED", "FULL"],
                start_time__lt=end,
                end_time__gt=start,
            )
            if room:
                ev_qs = ev_qs.filter(Q(room__isnull=True) | Q(room=room))
            if instance:
                ev_qs = ev_qs.exclude(pk=instance.pk)
            if ev_qs.exists():
                raise serializers.ValidationError("Chevauchement avec un évènement bloquant existant.")

        return data


class EvenementRegistrationListSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_first_name = serializers.CharField(source='user.first_name', read_only=True)
    user_last_name = serializers.CharField(source='user.last_name', read_only=True)

    class Meta:
        model = EvenementRegistration
        fields = ['id', 'user_id', 'user_email', 'user_first_name', 'user_last_name', 'created_at']


class EvenementRegistrationSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = EvenementRegistration
        fields = ['id', 'event', 'user', 'user_email', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']


# --- INVITES (in-app) ---
class EventLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evenement
        fields = ['id', 'title', 'date', 'start_time', 'end_time', 'status']


class EventInviteListSerializer(serializers.ModelSerializer):
    event = EventLiteSerializer(read_only=True)
    supplier_deadline_at = serializers.SerializerMethodField()

    class Meta:
        model = EventInvite
        fields = [
            'id', 'status', 'expires_at',
            'supplier_deadline_at',
            'event',
        ]

    def get_supplier_deadline_at(self, obj):
        dt = obj.supplier_deadline_at()
        return dt.isoformat() if dt else None


class EventInviteCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = EventInvite
        fields = ['id', 'event', 'invited_user', 'email', 'phone', 'expires_at', 'status']
        read_only_fields = ['id', 'status']

    def validate(self, attrs):
        if not (attrs.get('invited_user') or attrs.get('email') or attrs.get('phone')):
            raise serializers.ValidationError("Fournis 'invited_user' ou 'email' ou 'phone'.")
        return attrs

class RestaurantClosureSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantClosure
        fields = ['id', 'restaurant', 'date', 'reason', 'created_at']
        read_only_fields = ['id', 'created_at']