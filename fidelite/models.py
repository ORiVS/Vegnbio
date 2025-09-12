from django.conf import settings
from django.db import models
from django.utils import timezone
from decimal import Decimal

class LoyaltyProgram(models.Model):
    """
    Configuration globale du programme de fidélité.
    On suppose un seul enregistrement (utilise get_or_create côté code).
    """
    name = models.CharField(max_length=120, default="Veg'N Bio Rewards")
    description = models.TextField(blank=True)
    # Taux de gain: points gagnés par euro payé (ex: 1.0 => 1€ = 1 point)
    earn_rate_per_euro = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("1.00"))
    # Taux de conversion points -> euros (ex: 100 points = 1€ => redeem_rate_euro_per_point=0.01)
    redeem_rate_euro_per_point = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal("0.01"))
    rules = models.TextField(blank=True, help_text="Règles, seuils, bonus (texte libre).")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class Membership(models.Model):
    """
    Adhésion d'un utilisateur au programme: stocke le solde de points.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membership")
    joined_at = models.DateTimeField(default=timezone.now)
    points_balance = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user} - {self.points_balance} pts"


class PointsTransaction(models.Model):
    """
    Historique des points (gains, dépenses, ajustements).
    """
    EARN = "EARN"
    SPEND = "SPEND"
    ADJUST = "ADJUST"
    KIND_CHOICES = [(EARN, "Earn"), (SPEND, "Spend"), (ADJUST, "Adjust")]

    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="transactions")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    points = models.IntegerField()  # positif pour EARN/ADJUST+, négatif pour SPEND/ADJUST-
    reason = models.CharField(max_length=255, blank=True)
    related_order_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind} {self.points} pts ({self.reason})"
