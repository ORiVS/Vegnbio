from rest_framework import serializers
from .models import Restaurant, Room, Reservation, Evenement, EvenementRegistration, EventInvite
from datetime import datetime
from django.utils import timezone

class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ['id', 'name', 'capacity']


class RestaurantSerializer(serializers.ModelSerializer):
    rooms = RoomSerializer(many=True, read_only=True)

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


class ReservationSerializer(serializers.ModelSerializer):
    customer = serializers.HiddenField(default=serializers.CurrentUserDefault())
    room_name = serializers.SerializerMethodField()
    restaurant_name = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)  # client ne peut pas définir ce champ

    class Meta:
        model = Reservation
        fields = [
            'id', 'customer', 'restaurant', 'room', 'room_name', 'restaurant_name',
            'date', 'start_time', 'end_time',
            'status', 'full_restaurant', 'created_at'
        ]

        read_only_fields = ['created_at', 'room_name', 'restaurant_name', 'status']

    def get_room_name(self, obj):
        if obj.room:
            return obj.room.name
        return None

    def get_restaurant_name(self, obj):
        if obj.full_restaurant and obj.restaurant:
            return obj.restaurant.name
        elif obj.room and obj.room.restaurant:
            return obj.room.restaurant.name
        return None

    def validate(self, data):
        start = data['start_time']
        end = data['end_time']
        date = data['date']
        full_restaurant = data.get('full_restaurant', False)
        restaurant = data.get('restaurant')
        room = data.get('room')

        if full_restaurant and not restaurant:
            raise serializers.ValidationError("Vous devez spécifier un restaurant pour réserver l'ensemble.")

        if not full_restaurant and not room:
            raise serializers.ValidationError("Vous devez spécifier une salle pour réserver.")

        # ⛔ Réservation de restaurant entier → bloquer toutes les salles déjà prises
        if full_restaurant:
            conflicts = Reservation.objects.filter(
                restaurant=restaurant,
                date=date,
                start_time__lt=end,
                end_time__gt=start,
                full_restaurant=False  # une salle a été réservée
            )
            if conflicts.exists():
                raise serializers.ValidationError(
                    "Des salles sont déjà réservées sur ce créneau. Impossible de réserver tout le restaurant.")

        # ⛔ Réservation d'une salle → vérifier si restaurant entier déjà réservé
        if not full_restaurant and room:
            restaurant = room.restaurant
            conflicts = Reservation.objects.filter(
                restaurant=restaurant,
                date=date,
                start_time__lt=end,
                end_time__gt=start,
                full_restaurant=True
            )
            if conflicts.exists():
                raise serializers.ValidationError(
                    "Ce restaurant est déjà réservé en entier sur ce créneau. Impossible de réserver une salle.")

        # ⛔ Chevauchement dans la même salle
        if not full_restaurant and room:
            conflicts = Reservation.objects.filter(
                room=room,
                date=date,
                start_time__lt=end,
                end_time__gt=start,
            )
            if self.instance:
                conflicts = conflicts.exclude(pk=self.instance.pk)
            if conflicts.exists():
                raise serializers.ValidationError("Cette salle est déjà réservée sur ce créneau.")

        # Si le client réserve une salle, on déduit le restaurant automatiquement
        if not full_restaurant and room:
            data['restaurant'] = room.restaurant

        return data

class EvenementSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    current_registrations = serializers.IntegerField(source='registrations.count', read_only=True)

    class Meta:
        model = Evenement
        fields = [
            'id', 'restaurant', 'restaurant_name',
            'title', 'description', 'type',
            'date', 'start_time', 'end_time',
            'capacity', 'current_registrations',
            'is_public', 'status',
            'is_blocking', 'room',
            'rrule'
        ]

    def validate(self, data):
        # start < end
        if 'start_time' in data and 'end_time' in data:
            if data['start_time'] >= data['end_time']:
                raise serializers.ValidationError("start_time doit être avant end_time.")

        # si capacity < nb inscrits (cas update)
        instance = getattr(self, 'instance', None)
        if instance and 'capacity' in data and data['capacity'] is not None:
            if data['capacity'] < instance.registrations.count():
                raise serializers.ValidationError("La capacité ne peut pas être inférieure au nombre d’inscrits actuel.")

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

class EventInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventInvite
        fields = ['id', 'event', 'email', 'phone', 'token', 'status', 'created_at', 'expires_at']
        read_only_fields = ['id', 'token', 'status', 'created_at']

class EventInviteBulkCreateSerializer(serializers.Serializer):
    event = serializers.IntegerField()
    emails = serializers.ListField(
        child=serializers.EmailField(), allow_empty=False, required=True
    )

    def validate(self, data):
        from .models import Evenement
        event_id = data['event']
        try:
            data['event_obj'] = Evenement.objects.get(pk=event_id)
        except Evenement.DoesNotExist:
            raise serializers.ValidationError("Évènement introuvable.")
        return data