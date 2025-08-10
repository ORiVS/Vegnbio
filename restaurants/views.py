from datetime import datetime

from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from .models import Restaurant, Room, Reservation, Evenement, EvenementRegistration, EventInvite
from .permissions import IsClient, IsRestaurateur, IsAdminVegNBio
from .serializers import RestaurantSerializer, RoomSerializer, ReservationSerializer, EvenementSerializer, \
    EventInviteSerializer, EventInviteBulkCreateSerializer, EvenementRegistrationListSerializer
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as drf_status

from .utils import notify_event_full, send_invite_email, notify_event_cancelled


class RestaurantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Restaurant.objects.all().prefetch_related('rooms')
    serializer_class = RestaurantSerializer
    permission_classes = [permissions.AllowAny]  # ou [permissions.IsAuthenticated]

    @action(detail=True, methods=['get'], url_path='evenements',
            permission_classes=[permissions.AllowAny])
    def evenements(self, request, pk=None):
        qs = Evenement.objects.filter(restaurant_id=pk).order_by('date', 'start_time')
        data = EvenementSerializer(qs, many=True).data
        return Response(data)


class RoomViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Room.objects.select_related('restaurant').all()
    serializer_class = RoomSerializer
    permission_classes = [permissions.AllowAny]


class ReservationViewSet(viewsets.ModelViewSet):
    serializer_class = ReservationSerializer
    permission_classes = [IsClient]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'CLIENT':
            return Reservation.objects.filter(customer=user)
        elif user.role == 'RESTAURATEUR':
            return Reservation.objects.all()  # ou filtrer par salle si tu veux restreindre
        return Reservation.objects.none()

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)

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

        reservation.status = new_status
        reservation.save()
        return Response({'status': f"Réservation {reservation.id} mise à jour avec succès."})

    def update(self, request, *args, **kwargs):
        reservation = self.get_object()

        # Restriction : seules les réservations en attente peuvent être modifiées
        if reservation.status != 'PENDING':
            return Response({'error': 'Seules les réservations en attente peuvent être modifiées.'}, status=403)

        # Client peut modifier sa propre réservation
        if request.user.role == 'CLIENT' and reservation.customer != request.user:
            return Response({'error': 'Vous ne pouvez pas modifier cette réservation.'}, status=403)

        # Restaurateur peut modifier si la salle est dans son restaurant (optionnel selon ta logique)
        # ...

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        reservation = self.get_object()

        if reservation.status != 'PENDING':
            return Response(
                {"error": "Seules les réservations en attente peuvent être annulées."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Vérifie que le client est propriétaire OU que c’est un restaurateur
        if request.user.role == 'CLIENT' and reservation.customer != request.user:
            return Response({"error": "Vous ne pouvez pas annuler cette réservation."}, status=403)

        if request.user.role == 'RESTAURATEUR':
            # (Optionnel) : vérifier que la salle appartient à un restaurant du restaurateur
            pass  # ou ajouter ta logique

        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[IsClient | IsRestaurateur])
    def cancel(self, request, pk=None):
        reservation = self.get_object()

        if reservation.status != 'PENDING':
            return Response({"error": "Impossible d’annuler une réservation déjà traitée."}, status=403)

        # Vérification des droits
        if request.user.role == 'CLIENT' and reservation.customer != request.user:
            return Response({"error": "Vous ne pouvez pas annuler cette réservation."}, status=403)

        # (Optionnel) restaurateur vérifie appartenance
        # ...

        reservation.status = 'CANCELLED'
        reservation.save()
        return Response({"status": "Réservation annulée avec succès."})


@api_view(['GET'])
@permission_classes([IsRestaurateur])
def restaurant_reservations_view(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)

    if restaurant.owner != request.user:
        return Response({"detail": "Accès interdit."}, status=403)

    status_filter = request.GET.get('status')  # exemple : ?status=CONFIRMED

    reservations = Reservation.objects.filter(room__restaurant=restaurant)

    if status_filter:
        reservations = reservations.filter(status=status_filter.upper())

    serializer = ReservationSerializer(reservations, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsRestaurateur])
def availability_dashboard(request, restaurant_id):
    date_str = request.GET.get('date')
    if not date_str:
        return Response({"error": "Veuillez fournir une date au format YYYY-MM-DD."}, status=400)
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response({"error": "Format de date invalide."}, status=400)

    restaurant = get_object_or_404(Restaurant, id=restaurant_id)

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
@permission_classes([IsRestaurateur | IsAdminVegNBio])
def all_reservations_view(request):
    reservations = Reservation.objects.select_related('room', 'customer', 'room__restaurant').all()
    serializer = ReservationSerializer(reservations, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsRestaurateur | IsAdminVegNBio])
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

class EvenementViewSet(viewsets.ModelViewSet):
    queryset = Evenement.objects.select_related('restaurant').all()
    serializer_class = EvenementSerializer

    def get_permissions(self):
        # Création / modif / sup : restaurateur
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                           'publish', 'cancel', 'close', 'reopen']:
            return [IsAuthenticated(), IsRestaurateur()]
        # Inscription côté client
        if self.action in ['register', 'unregister']:
            return [IsAuthenticated()]
        # Lecture publique
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()

        # Lecture côté client : n’afficher que PUBLISHED (ou FULL/CANCELLED si tu veux)
        if self.request.method == 'GET' and not self.request.user.is_authenticated:
            qs = qs.filter(status='PUBLISHED', is_public=True)

        # Filtres
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
        # Restreindre : le restaurateur ne crée que pour ses restaurants
        restaurant = serializer.validated_data['restaurant']
        if restaurant.owner != self.request.user:
            return Response({"detail": "Vous ne pouvez créer que pour vos restaurants."}, status=403)
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        obj = self.get_object()
        if obj.restaurant.owner != self.request.user:
            return Response({"detail": "Accès interdit."}, status=403)
        serializer.save()

    # ----- Invitations (Restaurateur propriétaire) -----
    @action(detail=True, methods=['post'])
    def invite(self, request, pk=None):
        event = self.get_object()
        if event.restaurant.owner != request.user:
            return Response({"detail": "Accès interdit."}, status=403)

        serializer = EventInviteSerializer(data={**request.data, "event": event.id})
        serializer.is_valid(raise_exception=True)
        invite = serializer.save()
        # Envoi e‑mail (si email)
        base_url = request.build_absolute_uri('/').rstrip('/')
        send_invite_email(invite, base_url)
        sent = send_invite_email(invite, base_url)
        print("EMAIL_SENT_COUNT", sent)  # sent doit être 1 si OK avec SMTP

        return Response(EventInviteSerializer(invite).data, status=201)

    @action(detail=True, methods=['get'], url_path='registrations',
            permission_classes=[IsAuthenticated])
    def registrations(self, request, pk=None):
        event = self.get_object()

        # Seul le restaurateur owner (ou un admin si tu en as un) voit la liste complète
        is_owner = (event.restaurant.owner == request.user)
        is_admin = getattr(request.user, 'role', None) == 'ADMIN'

        if not (is_owner or is_admin):
            # Option A (simple) : l’utilisateur ne voit que SA propre inscription + le compteur
            mine = event.registrations.select_related('user').filter(user=request.user).first()
            return Response({
                "count": event.registrations.count(),
                "me": {
                    "registered": bool(mine),
                    "registered_at": getattr(mine, 'created_at', None)
                }
            })

        # Owner/admin → liste complète
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
        if event.restaurant.owner != request.user:
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

    # ----- Acceptation d’invitation (Client) -----
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

        # Capacité ?
        if event.capacity is not None and event.registrations.count() >= event.capacity:
            event.status = 'FULL'
            event.save()
            return Response({"detail": "Évènement complet."}, status=400)

        reg, created = EvenementRegistration.objects.get_or_create(event=event, user=request.user)
        if not created:
            return Response({"detail": "Déjà inscrit."}, status=400)

        invite.status = "ACCEPTED"
        invite.save()

        # Passage à FULL si on atteint la capacité
        if event.capacity is not None and event.registrations.count() >= event.capacity:
            event.status = 'FULL'
            event.save()
            notify_event_full(event)

        return Response({"status": "Invitation acceptée, inscription confirmée."}, status=201)


    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.restaurant.owner != request.user:
            return Response({"detail": "Accès interdit."}, status=403)
        return super().destroy(request, *args, **kwargs)

    # ----- Actions Restaurateur -----
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        obj = self.get_object()
        if obj.restaurant.owner != request.user:
            return Response({"detail": "Accès interdit."}, status=403)
        if obj.status not in ['DRAFT', 'CANCELLED']:
            return Response({"detail": "Déjà publié ou complet."}, status=400)
        obj.status = 'PUBLISHED'
        obj.save()
        return Response({"status": "Évènement publié."})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        obj = self.get_object()
        if obj.restaurant.owner != request.user:
            return Response({"detail": "Accès interdit."}, status=403)
        obj.status = 'CANCELLED'
        obj.save()
        notify_event_cancelled(obj)
        return Response({"status": "Évènement annulé."})

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        obj = self.get_object()
        if obj.restaurant.owner != request.user:
            return Response({"detail": "Accès interdit."}, status=403)
        obj.status = 'FULL'
        obj.save()
        notify_event_full(obj)
        return Response({"status": "Évènement marqué complet."})

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        obj = self.get_object()
        if obj.restaurant.owner != request.user:
            return Response({"detail": "Accès interdit."}, status=403)
        obj.status = 'PUBLISHED'
        obj.save()
        return Response({"status": "Évènement réouvert."})

    # ----- Actions Client -----
    @action(detail=True, methods=['post'])
    def register(self, request, pk=None):
        event = self.get_object()

        if event.status != 'PUBLISHED':
            return Response({"detail": "Inscriptions fermées."}, status=400)

        # Si privé → vérifier que l'utilisateur a une invitation (à implémenter côté notif/invit)
        if not event.is_public:
            # Vérifier une invitation valide liée à l'utilisateur
            # Critère minimal : email de l'utilisateur correspond à une invitation PENDING
            inv_qs = EventInvite.objects.filter(event=event, email=request.user.email, status="PENDING")
            invite = inv_qs.first()
            if not invite or not invite.is_valid():
                return Response({"detail": "Invitation requise pour s'inscrire à cet évènement."}, status=403)

        # Capacité
        if event.capacity is not None and event.registrations.count() >= event.capacity:
            event.status = 'FULL'
            event.save()
            return Response({"detail": "Évènement complet."}, status=400)

        reg, created = EvenementRegistration.objects.get_or_create(
            event=event, user=request.user
        )
        if not created:
            return Response({"detail": "Déjà inscrit."}, status=400)

        # Si on atteint la capacité exacte → passer à FULL
        if event.capacity is not None and event.registrations.count() >= event.capacity:
            event.status = 'FULL'
            event.save()

        return Response({"status": "Inscription confirmée."}, status=201)

    @action(detail=True, methods=['post'])
    def unregister(self, request, pk=None):
        event = self.get_object()
        deleted, _ = EvenementRegistration.objects.filter(event=event, user=request.user).delete()
        if not deleted:
            return Response({"detail": "Pas d'inscription trouvée."}, status=400)

        # Si c'était FULL et qu'une place se libère → repasser PUBLISHED
        if event.status == 'FULL':
            event.status = 'PUBLISHED'
            event.save()

        return Response({"status": "Désinscription effectuée."})

