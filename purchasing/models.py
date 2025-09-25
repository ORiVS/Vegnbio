from decimal import Decimal
from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError

from market.models import SupplierOffer

class SupplierOrder(models.Model):
    STATUS = [
        ("PENDING_SUPPLIER", "En attente producteur"),
        ("CONFIRMED", "Confirmée"),
        ("PARTIALLY_CONFIRMED", "Partiellement confirmée"),
        ("REJECTED", "Rejetée"),
        ("CANCELLED", "Annulée"),
    ]
    restaurateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="supplier_orders")
    supplier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="incoming_orders")
    status = models.CharField(max_length=24, choices=STATUS, default="PENDING_SUPPLIER")
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if getattr(self.restaurateur, "role", None) != "RESTAURATEUR":
            raise ValidationError("Seul un restaurateur peut passer commande.")
        if getattr(self.supplier, "role", None) != "FOURNISSEUR":
            raise ValidationError("Commande adressée à un non-fournisseur.")

    def __str__(self):
        return f"Order #{self.id} → supplier={self.supplier_id} status={self.status}"


class SupplierOrderItem(models.Model):
    order = models.ForeignKey(SupplierOrder, on_delete=models.CASCADE, related_name="items")
    offer = models.ForeignKey(SupplierOffer, on_delete=models.PROTECT, related_name="order_items")
    qty_requested = models.DecimalField(max_digits=12, decimal_places=2)
    qty_confirmed = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # prix au moment de la commande

    def clean(self):
        if self.qty_requested <= 0:
            raise ValidationError("Quantité demandée doit être positive.")
        # l'offre doit appartenir au supplier de la commande
        if self.order and self.offer.supplier_id != self.order.supplier_id:
            raise ValidationError("Offre ne correspond pas au fournisseur de la commande.")
        # produit bio et IDF
        if not self.offer.is_bio:
            raise ValidationError("Seuls des produits bio peuvent être commandés.")
        if self.offer.region not in getattr(settings, "REGIONS_ALLOWED", ["Île-de-France"]):
            raise ValidationError("Seuls des produits d'Île-de-France peuvent être commandés.")

    @property
    def total_requested(self):
        return (self.qty_requested or Decimal("0")) * (self.unit_price or Decimal("0"))
