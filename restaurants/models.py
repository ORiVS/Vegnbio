import secrets

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import time

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
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='reservations', blank=True, null=True)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='reservations', blank=True, null=True)
    full_restaurant = models.BooleanField(default=False)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # Vérifie l’ordre temporel
        if self.start_time >= self.end_time:
            raise ValidationError("L'heure de début doit être avant l'heure de fin.")

        # ⚠️ Si salle renseignée, vérifie collision exacte sur le créneau
        if self.room:
            if Reservation.objects.exclude(id=self.id).filter(
                room=self.room,
                date=self.date,
                start_time=self.start_time,
                end_time=self.end_time
            ).exists():
                raise ValidationError("Un créneau identique existe déjà pour cette salle.")

    def __str__(self):
        cible = self.room.name if self.room else f"Restaurant complet ({self.restaurant.name})"
        return f"{self.customer} - {cible} ({self.date} {self.start_time}-{self.end_time})"

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

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='evenements')
    title = models.CharField(max_length=100)
    description = models.TextField()
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError("L'heure de début doit être avant l'heure de fin.")

    def __str__(self):
        return f"{self.title} ({self.date} - {self.restaurant.name})"

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

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='evenements')
    title = models.CharField(max_length=100)
    description = models.TextField()
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    # Nouveaux champs
    capacity = models.PositiveIntegerField(null=True, blank=True, help_text="Nombre de places (optionnel)")
    is_public = models.BooleanField(default=True, help_text="Public ou sur invitation")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")

    # Si un évènement occupe le restaurant (ou une salle) et bloque les réservations
    is_blocking = models.BooleanField(default=False)
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True,
                             help_text="Si non null, évènement dans cette salle")

    # Récurrence simple (facultative)
    rrule = models.CharField(max_length=255, blank=True, null=True,
                             help_text="RRULE iCal ex: FREQ=WEEKLY;BYDAY=TU")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_time >= self.end_time:
            raise ValidationError("L'heure de début doit être avant l'heure de fin.")
        # Option: vérifie l'intérieur des heures d'ouverture du restaurant
        # (à activer pour forcer)
        # open_close = ...
        # if not (open_ok): raise ValidationError("En dehors des heures d’ouverture.")

    def __str__(self):
        return f"{self.title} ({self.date} - {self.restaurant.name})"

class EvenementRegistration(models.Model):
    event = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name='registrations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('event', 'user')  # un utilisateur ne s’inscrit qu’une fois


class EventInvite(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "En attente"),
        ("ACCEPTED", "Acceptée"),
        ("REVOKED", "Révoquée"),
    ]

    event = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name='invites')
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)  # si tu veux SMS plus tard
    token = models.CharField(max_length=64, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['event', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)[:64]
        # Optionnel: auto-expiration à J+14 si pas fourni
        if self.expires_at is None:
            self.expires_at = timezone.now() + timezone.timedelta(days=14)
        super().save(*args, **kwargs)

    def is_valid(self):
        return self.status == "PENDING" and (self.expires_at is None or self.expires_at >= timezone.now())

    def __str__(self):
        ident = self.email or self.phone or "contact"
        return f"Invite {ident} → {self.event.title}"