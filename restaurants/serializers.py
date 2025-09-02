from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Restaurant, Room, Reservation, Evenement, EvenementRegistration, EventInvite, RestaurantClosure
from datetime import datetime
from django.utils import timezone

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
    """Autorise l'édition de la fiche + horaires (owner only côté ViewSet)."""
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

class ReservationSerializer(serializers.ModelSerializer):
    # Par défaut (rôle CLIENT), le client = utilisateur courant
    customer = serializers.HiddenField(default=serializers.CurrentUserDefault())

    # NOUVEAU : création par restaurateur via e-mail uniquement
    customer_email = serializers.EmailField(write_only=True, required=False)

    # (optionnel: compat legacy si tu envoies encore un id quelque part)
    customer_id = serializers.IntegerField(write_only=True, required=False)

    # Champs d'affichage utiles au front
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
            'customer', 'customer_email', 'customer_id',            # <- write-only (email préféré)
            'customer_email_read', 'customer_first_name',
            'customer_last_name', 'customer_id_read',               # <- read-only
            'restaurant', 'room', 'room_name', 'restaurant_name',
            'date', 'start_time', 'end_time',
            'status', 'full_restaurant', 'created_at'
        ]
        read_only_fields = [
            'created_at', 'room_name', 'restaurant_name', 'status',
            'customer_email_read', 'customer_first_name',
            'customer_last_name', 'customer_id_read'
        ]

    def get_room_name(self, obj):
        return obj.room.name if obj.room else None

    def get_restaurant_name(self, obj):
        # Toujours renvoyer le nom si possible
        if obj.restaurant:
            return obj.restaurant.name
        if obj.room and obj.room.restaurant:
            return obj.room.restaurant.name
        return None

    def validate(self, data):
        start = data['start_time']
        end = data['end_time']
        date_ = data['date']
        full_restaurant = data.get('full_restaurant', False)
        restaurant = data.get('restaurant')
        room = data.get('room')

        today = timezone.localdate()
        now_t = timezone.localtime().time()
        if date_ < today:
            raise serializers.ValidationError("Impossible de réserver dans le passé.")
        if date_ == today and end <= now_t:
            raise serializers.ValidationError("Le créneau est déjà passé aujourd'hui.")
        if start >= end:
            raise serializers.ValidationError("L'heure de début doit être avant l'heure de fin.")

        if full_restaurant and not restaurant:
            raise serializers.ValidationError("Vous devez spécifier un restaurant pour réserver l'ensemble.")
        if not full_restaurant and not room:
            raise serializers.ValidationError("Vous devez spécifier une salle pour réserver.")

        # si salle => force restaurant pour les contrôles
        if not full_restaurant and room:
            data['restaurant'] = room.restaurant
            restaurant = room.restaurant

        if not restaurant:
            raise serializers.ValidationError("Restaurant introuvable pour valider les horaires d'ouverture.")
        if not restaurant.is_time_range_within_opening(date_, start, end):
            raise serializers.ValidationError("Créneau hors horaires d'ouverture du restaurant.")

        # Conflits
        if full_restaurant:
            conflicts = Reservation.objects.filter(
                restaurant=restaurant, date=date_,
                start_time__lt=end, end_time__gt=start, full_restaurant=False
            )
            if self.instance:
                conflicts = conflicts.exclude(pk=self.instance.pk)
            if conflicts.exists():
                raise serializers.ValidationError(
                    "Des salles sont déjà réservées sur ce créneau. Impossible de réserver tout le restaurant."
                )
        else:
            conflicts = Reservation.objects.filter(
                restaurant=restaurant, date=date_,
                start_time__lt=end, end_time__gt=start, full_restaurant=True
            )
            if self.instance:
                conflicts = conflicts.exclude(pk=self.instance.pk)
            if conflicts.exists():
                raise serializers.ValidationError(
                    "Ce restaurant est déjà réservé en entier sur ce créneau."
                )
            conflicts = Reservation.objects.filter(
                room=room, date=date_,
                start_time__lt=end, end_time__gt=start
            )
            if self.instance:
                conflicts = conflicts.exclude(pk=self.instance.pk)
            if conflicts.exists():
                raise serializers.ValidationError("Cette salle est déjà réservée sur ce créneau.")

        ev_qs = Evenement.objects.filter(
            restaurant=restaurant, date=date_, is_blocking=True,
            start_time__lt=end, end_time__gt=start, status__in=["PUBLISHED", "FULL"]
        )
        if not full_restaurant and room:
            from django.db.models import Q
            ev_qs = ev_qs.filter(Q(room__isnull=True) | Q(room=room))
        if ev_qs.exists():
            raise serializers.ValidationError("Créneau indisponible (événement bloquant).")

        return data

    def create(self, validated):
        """
        - CLIENT : 'customer' = CurrentUserDefault()
        - RESTAURATEUR : on IGNORE 'customer' et on le remplace par l'utilisateur résolu via 'customer_email'
          (ou 'customer_id' en secours legacy).
        """
        request = self.context.get('request')

        # Retirer systématiquement les write-only pour éviter doublons
        email = (validated.pop('customer_email', None) or "").strip()
        cid = validated.pop('customer_id', None)

        if request and getattr(request.user, 'role', None) == 'RESTAURATEUR':
            # Eviter le conflit avec HiddenField
            validated.pop('customer', None)

            # -> Email OBLIGATOIRE (politique demandée)
            if not email:
                raise serializers.ValidationError("customer_email est requis (création par restaurateur).")

            try:
                customer = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                raise serializers.ValidationError("Client introuvable pour ce customer_email.")

            validated['customer'] = customer
            return super().create(validated)

        # Rôle CLIENT : on ignore tout email/id éventuellement envoyés
        return super().create(validated)

# --- EVENTS (inchangé) ---
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
            'created_at','updated_at'
        ]
        read_only_fields = [
            'status','current_registrations',
            'published_at','full_at','cancelled_at',
            'created_at','updated_at'
        ]

    def validate(self, data):
        if 'start_time' in data and 'end_time' in data:
            if data['start_time'] >= data['end_time']:
                raise serializers.ValidationError("start_time doit être avant end_time.")
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


# --- FERMETURES ---
class RestaurantClosureSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantClosure
        fields = ['id', 'restaurant', 'date', 'reason', 'created_at']
        read_only_fields = ['id', 'created_at']
