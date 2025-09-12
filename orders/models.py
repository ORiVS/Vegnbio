from django.conf import settings
from django.db import models
from django.utils import timezone
from decimal import Decimal

class DeliverySlot(models.Model):
    """
    Créneaux de livraison proposés (ex: 2025-09-10 12:00 -> 13:00).
    """
    start = models.DateTimeField()
    end = models.DateTimeField()

    def __str__(self):
        return f"{self.start:%Y-%m-%d %H:%M} - {self.end:%H:%M}"


class Cart(models.Model):
    """
    Panier par utilisateur (un panier actif).
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def total(self):
        return sum((item.unit_price * item.quantity for item in self.items.all()), Decimal("0.00"))

    def __str__(self):
        return f"Cart({self.user})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    external_item_id = models.CharField(max_length=64, help_text="ID du plat/produit dans un autre service")
    name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("cart", "external_item_id")

    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.name} x{self.quantity}"


class Order(models.Model):
    PENDING = "PENDING"
    PREPARING = "PREPARING"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (PENDING, "En attente"),
        (PREPARING, "En préparation"),
        (OUT_FOR_DELIVERY, "En livraison"),
        (DELIVERED, "Livrée"),
        (CANCELLED, "Annulée"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)

    # Adresse de livraison (snapshot)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120)
    postal_code = models.CharField(max_length=20)
    phone = models.CharField(max_length=40, blank=True)

    # Créneau de livraison
    slot = models.ForeignKey(DeliverySlot, on_delete=models.PROTECT)

    # Totaux
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_points_used = models.IntegerField(default=0)
    discount_euros = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    def __str__(self):
        return f"Order #{self.id} - {self.user} - {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    external_item_id = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    def save(self, *args, **kwargs):
        self.line_total = self.unit_price * self.quantity
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} x{self.quantity}"
