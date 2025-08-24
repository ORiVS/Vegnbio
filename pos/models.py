from decimal import Decimal
from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from restaurants.models import Restaurant
from menu.models import Dish  # vendu à la caisse

class Order(models.Model):
    STATUS = [
        ("OPEN", "Ouverte"),
        ("HOLD", "En attente"),
        ("PAID", "Payée"),
        ("CANCELLED", "Annulée"),
        ("REFUNDED", "Remboursée"),
    ]

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="orders")
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="pos_orders")
    status = models.CharField(max_length=12, choices=STATUS, default="OPEN")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("10.00"),
                                   help_text="TVA % (ex: 10.00)")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"),
                                           help_text="Remise % (0-100)")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    change_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    note = models.CharField(max_length=255, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]
        indexes = [models.Index(fields=["restaurant", "opened_at"])]

    def __str__(self):
        return f"Order #{self.pk} - {self.restaurant.name} [{self.status}]"

    def ensure_mutable(self):
        if self.status not in ["OPEN", "HOLD"]:
            raise ValidationError("Commande non modifiable (déjà payée/annulée).")

    def recalc_totals(self):
        # ⚠️ Requête fraîche, aucune dépendance au cache de prefetch
        items = OrderItem.objects.filter(order_id=self.pk)

        self.subtotal = sum((it.unit_price * it.quantity for it in items), Decimal("0.00"))

        discount = self.discount_amount or Decimal("0.00")
        if self.discount_percent and self.discount_percent > 0:
            discount += (self.subtotal * self.discount_percent / Decimal("100"))

        net = self.subtotal - discount
        if net < 0:
            net = Decimal("0.00")

        self.tax_total = (net * self.tax_rate / Decimal("100")).quantize(Decimal("0.01"))
        self.total_due = (net + self.tax_total).quantize(Decimal("0.01"))
        self.change_due = (self.paid_amount - self.total_due) if self.paid_amount > self.total_due else Decimal("0.00")

    def close_if_paid(self):
        if self.total_due <= self.paid_amount and self.status != "PAID":
            self.status = "PAID"
            self.closed_at = timezone.now()


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    dish = models.ForeignKey(Dish, on_delete=models.SET_NULL, null=True, blank=True)
    custom_name = models.CharField(max_length=120, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def clean(self):
        if not self.dish and not self.custom_name:
            raise ValidationError("Fournir 'dish' OU 'custom_name'.")
        if self.quantity < 1:
            raise ValidationError("Quantité >= 1 requise.")
        if self.unit_price < 0:
            raise ValidationError("Prix unitaire invalide.")

    def __str__(self):
        label = self.custom_name or (self.dish.name if self.dish else "item")
        return f"{label} x{self.quantity}"

class Payment(models.Model):
    METHOD = [
        ("CASH", "Espèces"),
        ("CARD", "Carte"),
        ("ONLINE", "En ligne"),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField(max_length=12, choices=METHOD)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    received_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.method} {self.amount}€ pour Order #{self.order_id}"
