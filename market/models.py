from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

# Référence allergènes du module Menus
from menu.models import Allergen

REGION_IDF = "Île-de-France"
REGIONS_ALLOWED = [REGION_IDF]  # extensible

class SupplierOffer(models.Model):
    STATUS = [
        ("DRAFT", "Brouillon"),
        ("PUBLISHED", "Publiée"),
        ("UNLISTED", "Retirée"),
        ("FLAGGED", "Signalée"),
    ]
    supplier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="offers")
    product_name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_bio = models.BooleanField(default=True)
    producer_name = models.CharField(max_length=120, blank=True, null=True)
    region = models.CharField(max_length=120, default=REGION_IDF)
    allergens = models.ManyToManyField(Allergen, blank=True, related_name="supplier_offers")

    unit = models.CharField(max_length=32, default="kg")  # kg, pièce, botte...
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    min_order_qty = models.DecimalField(max_digits=10, decimal_places=2, default=1, validators=[MinValueValidator(0.01)])
    stock_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])

    available_from = models.DateField(null=True, blank=True)
    available_to   = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=16, choices=STATUS, default="DRAFT")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self.region not in REGIONS_ALLOWED:
            raise ValidationError("Région non autorisée. Exigence de local: Île-de-France.")
        if self.available_from and self.available_to and self.available_to < self.available_from:
            raise ValidationError("available_to doit être ≥ available_from.")
        if self.supplier and getattr(self.supplier, "role", None) != "FOURNISSEUR":
            raise ValidationError("Seuls les utilisateurs FOURNISSEUR peuvent créer des offres.")

    def is_available_on(self, date):
        if self.available_from and date < self.available_from: return False
        if self.available_to and date > self.available_to: return False
        return self.stock_qty > 0

    def __str__(self):
        return f"{self.product_name} ({self.region}) [{self.status}]"


class OfferReview(models.Model):
    offer = models.ForeignKey(SupplierOffer, on_delete=models.CASCADE, related_name="reviews")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="offer_reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])  # 1..5 (on validera ≤5 en serializer)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("offer", "author")
        ordering = ["-created_at"]


class OfferReport(models.Model):
    STATUS = [("NEW", "Nouveau"), ("REVIEWED", "Examiné"), ("ACTION_TAKEN", "Action prise")]
    offer = models.ForeignKey(SupplierOffer, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="offer_reports")
    reason = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS, default="NEW")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
