import secrets
from datetime import time, timedelta, datetime as ddatetime, time as dtime

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Restaurant(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    capacity = models.PositiveIntegerField(help_text="Nombre total de places assises")

    # Services disponibles
    wifi_available = models.BooleanField(default=True)
    printer_available = models.BooleanField(default=True)
    member_trays_available = models.BooleanField(default=False, help_text="Plateaux membres")
    delivery_trays_available = models.BooleanField(default=False, help_text="Plateaux repas livrables")
    animations_enabled = models.BooleanField(default=False, help_text="Animations/conférences disponibles")
    animation_day = models.CharField(max_length=20, blank=True, null=True, help_text="Jour des animations (ex: Mardi)")

    # Horaires détaillés
    opening_time_mon_to_thu = models.TimeField(default=time(9, 0))
    closing_time_mon_to_thu = models.TimeField(default=time(23, 59))

    opening_time_friday = models.TimeField(default=time(9, 0))
    closing_time_friday = models.TimeField(default=time(1, 0))  # 1h du matin samedi

    opening_time_saturday = models.TimeField(default=time(9, 0))
    closing_time_saturday = models.TimeField(default=time(5, 0))  # 5h du matin dimanche

    opening_time_sunday = models.TimeField(default=time(11, 0))
    closing_time_sunday = models.TimeField(default=time(23, 59))

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='restaurants',
        limit_choices_to={'role': 'RESTAURATEUR'}
    )

    def __str__(self):
        return f"{self.name} - {self.city}"

    class Meta:
        verbose_name = "Restaurant"
        verbose_name_plural = "Restaurants"
        ordering = ['name']

    def opening_times_for_weekday(self, weekday: int):
        if weekday in [0, 1, 2, 3]:
            return (self.opening_time_mon_to_thu, self.closing_time_mon_to_thu)
        if weekday == 4:
            return (self.opening_time_friday, self.closing_time_friday)
        if weekday == 5:
            return (self.opening_time_saturday, self.closing_time_saturday)
        return (self.opening_time_sunday, self.closing_time_sunday)

    def is_time_range_within_opening(self, date_, start_t: time, end_t: time) -> bool:
        wd = date_.weekday()
        open_t, close_t = self.opening_times_for_weekday(wd)

        def in_range_same_day(open_t, close_t, st, et):
            if close_t > open_t:
                return (st >= open_t) and (et <= close_t)
            # overnight (ex: 09:00 → 01:00 le lendemain)
            return (st >= open_t) and (et <= time(23, 59, 59))

        ok_today = in_range_same_day(open_t, close_t, start_t, end_t)

        from datetime import time as ttime
        prev_open, prev_close = self.opening_times_for_weekday((wd - 1) % 7)
        is_prev_overnight = prev_close <= prev_open
        ok_prev_spill = False
        if is_prev_overnight:
            if (start_t >= ttime(0, 0, 0)) and (end_t <= prev_close):
                ok_prev_spill = True

        return ok_today or ok_prev_spill


class Room(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='rooms')
    name = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.name} - {self.restaurant.name}"

    class Meta:
        unique_together = ('restaurant', 'name')
        ordering = ['restaurant', 'name']
        verbose_name = "Salle"
        verbose_name_plural = "Salles"


class Reservation(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'En attente'),
        ('CONFIRMED', 'Confirmée'),
        ('CANCELLED', 'Annulée'),
    ]

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reservations')
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='reservations')

    party_size = models.PositiveIntegerField(help_text="Nombre de couverts demandés")

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='reservations', blank=True, null=True)
    full_restaurant = models.BooleanField(default=False, help_text="Réservation de tout le restaurant (décision resto)")

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError("L'heure de début doit être avant l'heure de fin.")

    def __str__(self):
        cible = "Tout le restaurant" if self.full_restaurant else (self.room.name if self.room else "À affecter")
        return f"{self.customer} - {self.restaurant.name} / {cible} ({self.date} {self.start_time}-{self.end_time})"

    class Meta:
        ordering = ['-date', 'start_time']


class Evenement(models.Model):
    TYPE_CHOICES = [
        ("ANNIVERSAIRE", "Anniversaire"),
        ("CONFERENCE", "Conférence"),
        ("SEMINAIRE", "Séminaire"),
        ("ANIMATION", "Animation"),
        ("AUTRE", "Autre"),
    ]
    STATUS_CHOICES = [
        ("DRAFT", "Brouillon"),
        ("PUBLISHED", "Publié"),
        ("FULL", "Complet"),
        ("CANCELLED", "Annulé"),
    ]

    restaurant = models.ForeignKey('Restaurant', on_delete=models.CASCADE, related_name='evenements')
    title = models.CharField(max_length=100)
    description = models.TextField()
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    capacity = models.PositiveIntegerField(null=True, blank=True, help_text="Nombre de places (optionnel)")
    is_public = models.BooleanField(default=True, help_text="Public ou sur invitation")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")

    is_blocking = models.BooleanField(default=False)
    room = models.ForeignKey('Room', on_delete=models.SET_NULL, null=True, blank=True,
                             help_text="Si non null, évènement dans cette salle")

    rrule = models.CharField(max_length=255, blank=True, null=True,
                             help_text="RRULE iCal ex: FREQ=WEEKLY;BYDAY=TU")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    full_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # Invitations fournisseurs
    requires_supplier_confirmation = models.BooleanField(
        default=False,
        help_text="Si vrai, les invitations 'producteurs' doivent être acceptées avant une date limite."
    )
    supplier_deadline_days = models.PositiveSmallIntegerField(
        default=14,
        help_text="Nombre de jours avant la date de l’événement : date limite d’acceptation pour les producteurs."
    )

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError("L'heure de début doit être avant l'heure de fin.")

    def supplier_deadline_at(self):
        """
        Date/heure limite locale (23:59:59) – compatible zoneinfo (pas de pytz.localize).
        """
        if not self.date or not self.requires_supplier_confirmation:
            return None
        limit_date = self.date - timedelta(days=int(self.supplier_deadline_days or 0))
        naive = ddatetime.combine(limit_date, dtime(23, 59, 59))
        tz = timezone.get_current_timezone()
        if timezone.is_naive(naive):
            return naive.replace(tzinfo=tz)
        return naive.astimezone(tz)

    def __str__(self):
        return f"{self.title} ({self.date} - {self.restaurant.name})"

    class Meta:
        ordering = ['date', 'start_time']
        indexes = [
            models.Index(fields=['restaurant', 'date']),
            models.Index(fields=['status']),
        ]


class EvenementRegistration(models.Model):
    event = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name='registrations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('event', 'user')


class EventInvite(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "En attente"),
        ("ACCEPTED", "Acceptée"),
        ("REVOKED", "Révoquée"),
        ("DECLINED", "Refusée"),
    ]

    event = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name='invites')

    # Ciblage : par utilisateur connecté (in-app) OU par email/téléphone (email+deeplink)
    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='event_invites',
        limit_choices_to={'role': 'FOURNISSEUR'}
    )
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)

    token = models.CharField(max_length=64, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['event', 'status']),
            models.Index(fields=['invited_user', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)[:64]
        if self.expires_at is None:
            self.expires_at = timezone.now() + timedelta(days=14)
        super().save(*args, **kwargs)

    def supplier_deadline_at(self):
        return self.event.supplier_deadline_at()

    def is_valid(self):
        if self.status != "PENDING":
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        # Si deadline fournisseur activée, la respecter aussi
        sdl = self.supplier_deadline_at()
        if sdl and timezone.now() > sdl:
            return False
        return True

    def __str__(self):
        ident = self.invited_user or self.email or self.phone or "contact"
        return f"Invite {ident} → {self.event.title}"


class RestaurantClosure(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='closures')
    date = models.DateField()
    reason = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('restaurant', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"Fermeture {self.restaurant.name} le {self.date} ({self.reason or '—'})"
