from datetime import datetime
from django.utils import timezone
from django.db.models import Q

from django.db import transaction
from django.contrib.auth import get_user_model
from rest_framework import viewsets, permissions, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from .models import Restaurant, Room, Reservation, Evenement, EvenementRegistration, EventInvite, RestaurantClosure
from .permissions import IsClient, IsRestaurateur, IsAdminVegNBio
from .serializers import (
    RestaurantSerializer, RestaurantUpdateSerializer,
    RoomReadSerializer, RoomWriteSerializer,
    ReservationSerializer, EvenementSerializer,
    EventInviteSerializer, EventInviteBulkCreateSerializer,
    EvenementRegistrationListSerializer, RestaurantClosureSerializer
)
from rest_framework.permissions import IsAuthenticated
from rest_framework import status as drf_status

from .utils import notify_event_full, send_invite_email, notify_event_cancelled
from rest_framework.exceptions import PermissionDenied


User = get_user_model()


# -------- RESTAURANT --------
class RestaurantViewSet(viewsets.ModelViewSet):
    queryset = Restaurant.objects.all().prefetch_related('rooms')
    serializer_class = RestaurantSerializer

    def get_permissions(self):
        # lecture publique
        if self.action in ['list', 'retrieve', 'evenements']:
            return [permissions.AllowAny()]
        # édition: restaurateur propriétaire ou admin
        if self.action in ['update', 'partial_update']:
            return [IsAuthenticated()]
        # interdiction de create/destroy par défaut (admin pourrait le faire si besoin)
        if self.action in ['create', 'destroy']:
            return [IsAuthenticated(), IsAdminVegNBio()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return RestaurantUpdateSerializer
        return RestaurantSerializer

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        if not (getattr(request.user, 'role', None) == 'ADMIN' or obj.owner == request.user):
            return Response({"detail": "Accès interdit."}, status=403)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        if not (getattr(request.user, 'role', None) == 'ADMIN' or obj.owner == request.user):
            return Response({"detail": "Accès interdit."}, status=403)
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=['get'], url_path='evenements',
            permission_classes=[permissions.AllowAny])
    def evenements(self, request, pk=None):
        qs = Evenement.objects.filter(restaurant_id=pk).order_by('date', 'start_time')
        data = EvenementSerializer(qs, many=True).data
        return Response(data)


# -------- ROOMS --------
class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.select_related('restaurant').all()

    def get_permissions(self):
        # Lecture publique autorisée
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        # Écriture restreinte
        return [IsAuthenticated(), IsRestaurateur()]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return RoomWriteSerializer
        return RoomReadSerializer

    def perform_create(self, serializer):
        restaurant = serializer.validated_data['restaurant']
        if restaurant.owner != self.request.user:
            raise permissions.PermissionDenied("Vous ne pouvez créer des salles que pour vos restaurants.")
        serializer.save()

    def perform_update(self, serializer):
        obj = self.get_object()
        if obj.restaurant.owner != self.request.user:
            raise permissions.PermissionDenied("Accès interdit.")
        # si le restaurateur change de restaurant via payload, revalider ownership
        new_restaurant = serializer.validated_data.get('restaurant', obj.restaurant)
        if new_restaurant.owner != self.request.user:
            raise permissions.PermissionDenied("Accès interdit (restaurant).")
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.restaurant.owner != request.user:
            return Response({"detail": "Accès interdit."}, status=403)
        return super().destroy(request, *args, **kwargs)


# -------- RESERVATIONS --------
class ReservationViewSet(viewsets.ModelViewSet):
    serializer_class = ReservationSerializer

    def get_permissions(self):
        # modérer: restaurateur
        if self.action in ['moderate']:
            return [IsAuthenticated(), IsRestaurateur()]
        # tout le reste: utilisateur authentifié (client ou restaurateur)
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'role', None) == 'CLIENT':
            return Reservation.objects.filter(customer=user)
        elif getattr(user, 'role', None) == 'RESTAURATEUR':
            # Un restaurateur voit toutes les réservations (ou on peut filtrer par ses restos)
            return Reservation.objects.all()
        return Reservation.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, 'role', None) == 'RESTAURATEUR':
            # vérifie ownership sur la cible (room/restaurant)
            room = serializer.validated_data.get('room')
            restaurant = serializer.validated_data.get('restaurant') or (room.restaurant if room else None)
            if not restaurant or restaurant.owner != user:
                raise permissions.PermissionDenied("Accès interdit: restaurant non possédé.")
            # le serializer gère customer_id -> customer
            serializer.save()
        else:
            # client standard
            serializer.save(customer=user)

    @action(detail=False, methods=['get'], permission_classes=[IsClient])
    def my_reservations(self, request):
        reservations = self.get_queryset()
        serializer = self.get_serializer(reservations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsRestaurateur])
    def moderate(self, request, pk=None):
        reservation = self.get_object()
        new_status = request.data.get('status')

        if new_status not in ['CONFIRMED', 'CANCELLED']:
            return Response({'error': 'Statut invalide.'}, status=drf_status.HTTP_400_BAD_REQUEST)

        # contrôle ownership
        target_restaurant = reservation.room.restaurant if reservation.room else reservation.restaurant
        if not target_restaurant or target_restaurant.owner != request.user:
            return Response({'error': "Accès interdit."}, status=403)

        reservation.status = new_status
        reservation.save()
        return Response({'status': f"Réservation {reservation.id} mise à jour avec succès."})

    def update(self, request, *args, **kwargs):
        reservation = self.get_object()
        if reservation.status != 'PENDING':
            return Response({'error': 'Seules les réservations en attente peuvent être modifiées.'}, status=403)

        if getattr(request.user, 'role', None) == 'CLIENT' and reservation.customer != request.user:
            return Response({'error': 'Vous ne pouvez pas modifier cette réservation.'}, status=403)

        if getattr(request.user, 'role', None) == 'RESTAURATEUR':
            target_restaurant = reservation.room.restaurant if reservation.room else reservation.restaurant
            if not target_restaurant or target_restaurant.owner != request.user:
                return Response({'error': 'Accès interdit.'}, status=403)

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        reservation = self.get_object()

        if reservation.status != 'PENDING':
            return Response(
                {"error": "Seules les réservations en attente peuvent être annulées."},
                status=status.HTTP_403_FORBIDDEN
            )

        if getattr(request.user, 'role', None) == 'CLIENT' and reservation.customer != request.user:
            return Response({"error": "Vous ne pouvez pas annuler cette réservation."}, status=403)

        if getattr(request.user, 'role', None) == 'RESTAURATEUR':
            target_restaurant = reservation.room.restaurant if reservation.room else reservation.restaurant
            if not target_restaurant or target_restaurant.owner != request.user:
                return Response({'error': 'Accès interdit.'}, status=403)

        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[IsClient | IsRestaurateur])
    def cancel(self, request, pk=None):
        reservation = self.get_object()

        if reservation.status != 'PENDING':
            return Response({"error": "Impossible d’annuler une réservation déjà traitée."}, status=403)

        if getattr(request.user, 'role', None) == 'CLIENT' and reservation.customer != request.user:
            return Response({"error": "Vous ne pouvez pas annuler cette réservation."}, status=403)

        if getattr(request.user, 'role', None) == 'RESTAURATEUR':
            target_restaurant = reservation.room.restaurant if reservation.room else reservation.restaurant
            if not target_restaurant or target_restaurant.owner != request.user:
                return Response({'error': 'Accès interdit.'}, status=403)

        reservation.status = 'CANCELLED'
        reservation.save()
        return Response({"status": "Réservation annulée avec succès."})

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsRestaurateur])
def restaurant_reservations_view(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    if restaurant.owner != request.user:
        return Response({"detail": "Accès interdit."}, status=403)

    status_filter = request.GET.get('status')

    # ⬇️ Inclure les réservations de salles ET les réservations "restaurant entier"
    qs = (
        Reservation.objects
        .select_related('restaurant', 'room', 'room__restaurant', 'customer')
        .filter(Q(room__restaurant=restaurant) | Q(restaurant=restaurant))
        .order_by('-date', 'start_time')
    )

    if status_filter:
        qs = qs.filter(status=status_filter.upper())

    serializer = ReservationSerializer(qs, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsRestaurateur])
def availability_dashboard(request, restaurant_id):
    date_str = request.GET.get('date')
    if not date_str:
        return Response({"error": "Veuillez fournir une date au format YYYY-MM-DD."}, status=400)
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response({"error": "Format de date invalide."}, status=400)

    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    # contrôle owner (sécurisation)
    if restaurant.owner != request.user and getattr(request.user, 'role', None) != 'ADMIN':
        return Response({"detail": "Accès interdit."}, status=403)

    rooms_payload = []
    for room in restaurant.rooms.all():
        reservations = room.reservations.filter(date=date).values('start_time', 'end_time', 'status')
        rooms_payload.append({
            "room": room.name,
            "capacity": room.capacity,
            "reservations": list(reservations)
        })

    events_qs = restaurant.evenements.filter(date=date).values(
        'id', 'title', 'type', 'start_time', 'end_time', 'status', 'is_public', 'capacity'
    )

    return Response({
        "date": str(date),
        "restaurant": restaurant.name,
        "rooms": rooms_payload,
        "evenements": list(events_qs)
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsRestaurateur | IsAdminVegNBio])
def all_reservations_view(request):
    reservations = Reservation.objects.select_related('room', 'customer', 'room__restaurant').all()
    serializer = ReservationSerializer(reservations, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsRestaurateur | IsAdminVegNBio])
def reservations_stats_view(request):
    restaurants = Restaurant.objects.prefetch_related('rooms__reservations').all()
    data = []

    for restaurant in restaurants:
        room_stats = []
        total, confirmed, pending, cancelled = 0, 0, 0, 0

        for room in restaurant.rooms.all():
            room_reservations = room.reservations.all()
            r_total = room_reservations.count()
            r_confirmed = room_reservations.filter(status='CONFIRMED').count()
            r_pending = room_reservations.filter(status='PENDING').count()
            r_cancelled = room_reservations.filter(status='CANCELLED').count()

            room_stats.append({
                "room": room.name,
                "total": r_total,
                "confirmed": r_confirmed,
                "pending": r_pending,
                "cancelled": r_cancelled
            })

            total += r_total
            confirmed += r_confirmed
            pending += r_pending
            cancelled += r_cancelled

        data.append({
            "restaurant": restaurant.name,
            "total_reservations": total,
            "confirmed": confirmed,
            "pending": pending,
            "cancelled": cancelled,
            "salles": room_stats
        })

    return Response(data)


# -------- EVENEMENTS (inchangé sauf sécurités déjà présentes) --------
class EvenementViewSet(viewsets.ModelViewSet):
    queryset = Evenement.objects.select_related('restaurant').all()
    serializer_class = EvenementSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                           'publish', 'cancel', 'close', 'reopen', 'invite', 'invite_bulk', 'registrations']:
            return [IsAuthenticated()]
        if self.action in ['register', 'unregister', 'accept_invite']:
            return [IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.method == 'GET' and not self.request.user.is_authenticated:
            qs = qs.filter(status='PUBLISHED', is_public=True)

        p = self.request.query_params
        if p.get('restaurant'):
            qs = qs.filter(restaurant_id=p['restaurant'])
        if p.get('date'):
            qs = qs.filter(date=p['date'])
        if p.get('type'):
            qs = qs.filter(type=p['type'])
        if p.get('status'):
            qs = qs.filter(status=p['status'])
        if p.get('is_public') in ['true', 'false']:
            qs = qs.filter(is_public=(p['is_public'] == 'true'))

        return qs

    def perform_create(self, serializer):
        restaurant = serializer.validated_data['restaurant']
        if restaurant.owner != self.request.user:
            # AVANT: return Response(..., status=403) ❌
            # MAINTENANT:
            raise PermissionDenied("Vous ne pouvez créer que pour vos restaurants.")
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        obj = self.get_object()
        if obj.restaurant.owner != self.request.user and getattr(self.request.user, 'role', None) != 'ADMIN':
            # AVANT: return Response(..., status=403) ❌
            raise PermissionDenied("Accès interdit.")
        serializer.save()

    @action(detail=True, methods=['post'])
    def invite(self, request, pk=None):
        event = self.get_object()
        if event.restaurant.owner != request.user and getattr(request.user, 'role', None) != 'ADMIN':
            return Response({"detail": "Accès interdit."}, status=403)

        serializer = EventInviteSerializer(data={**request.data, "event": event.id})
        serializer.is_valid(raise_exception=True)
        invite = serializer.save()
        base_url = request.build_absolute_uri('/').rstrip('/')
        send_invite_email(invite, base_url)
        return Response(EventInviteSerializer(invite).data, status=201)

    @action(detail=True, methods=['get'], url_path='registrations',
            permission_classes=[IsAuthenticated])
    def registrations(self, request, pk=None):
        event = self.get_object()
        is_owner = (event.restaurant.owner == request.user)
        is_admin = getattr(request.user, 'role', None) == 'ADMIN'

        if not (is_owner or is_admin):
            mine = event.registrations.select_related('user').filter(user=request.user).first()
            return Response({
                "count": event.registrations.count(),
                "me": {
                    "registered": bool(mine),
                    "registered_at": getattr(mine, 'created_at', None)
                }
            })

        qs = event.registrations.select_related('user').order_by('created_at')
        data = EvenementRegistrationListSerializer(qs, many=True).data
        return Response({
            "event_id": event.id,
            "event_title": event.title,
            "count": qs.count(),
            "registrations": data
        })

    @action(detail=True, methods=['post'])
    def invite_bulk(self, request, pk=None):
        event = self.get_object()
        if event.restaurant.owner != request.user and getattr(request.user, 'role', None) != 'ADMIN':
            return Response({"detail": "Accès interdit."}, status=403)

        payload = {"event": event.id, "emails": request.data.get('emails', [])}
        serializer = EventInviteBulkCreateSerializer(data=payload)
        serializer.is_valid(raise_exception=True)

        created = []
        base_url = request.build_absolute_uri('/').rstrip('/')

        with transaction.atomic():
            for email in serializer.validated_data['emails']:
                inv = EventInvite.objects.create(event=event, email=email)
                created.append(inv)
                send_invite_email(inv, base_url)

        return Response(EventInviteSerializer(created, many=True).data, status=201)

    @action(detail=True, methods=['post'])
    def accept_invite(self, request, pk=None):
        event = self.get_object()
        token = request.data.get('token')
        if not token:
            return Response({"detail": "Token requis."}, status=400)

        try:
            invite = EventInvite.objects.get(event=event, token=token)
        except EventInvite.DoesNotExist:
            return Response({"detail": "Invitation introuvable."}, status=404)

        if not invite.is_valid():
            return Response({"detail": "Invitation expirée ou invalide."}, status=400)

        if event.capacity is not None and event.registrations.count() >= event.capacity:
            event.status = 'FULL'
            event.save()
            return Response({"detail": "Évènement complet."}, status=400)

        reg, created = EvenementRegistration.objects.get_or_create(event=event, user=request.user)
        if not created:
            return Response({"detail": "Déjà inscrit."}, status=400)

        invite.status = "ACCEPTED"
        invite.save()

        if event.capacity is not None and event.registrations.count() >= event.capacity:
            event.status = 'FULL'
            event.full_at = timezone.now()
            event.save(update_fields=['status', 'full_at', 'updated_at'])
            notify_event_full(event)

        return Response({"status": "Invitation acceptée, inscription confirmée."}, status=201)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.restaurant.owner != request.user and getattr(request.user, 'role', None) != 'ADMIN':
            return Response({"detail": "Accès interdit."}, status=403)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        obj = self.get_object()
        if obj.restaurant.owner != request.user and getattr(request.user, 'role', None) != 'ADMIN':
            return Response({"detail": "Accès interdit."}, status=403)
        if obj.status not in ['DRAFT', 'CANCELLED']:
            return Response({"detail": "Déjà publié ou complet."}, status=400)
        obj.status = 'PUBLISHED'
        obj.published_at = timezone.now()
        obj.save(update_fields=['status', 'published_at', 'updated_at'])
        return Response({"status": "Évènement publié.", "published_at": obj.published_at})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        obj = self.get_object()
        if obj.restaurant.owner != request.user and getattr(request.user, 'role', None) != 'ADMIN':
            return Response({"detail": "Accès interdit."}, status=403)
        obj.status = 'CANCELLED'
        obj.cancelled_at = timezone.now()
        obj.save(update_fields=['status', 'cancelled_at', 'updated_at'])
        notify_event_cancelled(obj)
        return Response({"status": "Évènement annulé.", "cancelled_at": obj.cancelled_at})

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        obj = self.get_object()
        if obj.restaurant.owner != request.user and getattr(request.user, 'role', None) != 'ADMIN':
            return Response({"detail": "Accès interdit."}, status=403)
        obj.status = 'FULL'
        obj.full_at = timezone.now()
        obj.save(update_fields=['status', 'full_at', 'updated_at'])
        notify_event_full(obj)
        return Response({"status": "Évènement marqué complet.", "full_at": obj.full_at})

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        obj = self.get_object()
        if obj.restaurant.owner != request.user and getattr(request.user, 'role', None) != 'ADMIN':
            return Response({"detail": "Accès interdit."}, status=403)
        obj.status = 'PUBLISHED'
        obj.save(update_fields=['status', 'updated_at'])
        return Response({"status": "Évènement réouvert."})


# -------- FERMETURES --------
class RestaurantClosureViewSet(viewsets.ModelViewSet):
    queryset = RestaurantClosure.objects.select_related('restaurant').all()
    serializer_class = RestaurantClosureSerializer

    def get_permissions(self):
        # lecture possible pour owner / admin uniquement (on peut étendre)
        if self.action in ['list', 'retrieve', 'create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsRestaurateur()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, 'role', None) == 'ADMIN':
            return qs
        # ne voir que ses fermetures
        return qs.filter(restaurant__owner=user)

    def perform_create(self, serializer):
        restaurant = serializer.validated_data.get('restaurant')
        if not restaurant or restaurant.owner != self.request.user:
            raise permissions.PermissionDenied("Accès interdit: restaurant non possédé.")
        serializer.save()

    def perform_update(self, serializer):
        obj = self.get_object()
        if obj.restaurant.owner != self.request.user:
            raise permissions.PermissionDenied("Accès interdit.")
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.restaurant.owner != request.user:
            return Response({"detail": "Accès interdit."}, status=403)
        return super().destroy(request, *args, **kwargs)
