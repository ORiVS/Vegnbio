from django.conf import settings
from django.db import models
from django.utils import timezone
from decimal import Decimal
from restaurants.models import Restaurant
from menu.models import Dish

class DeliverySlot(models.Model):
    """
    Créneaux gérés par CHAQUE restaurant.
    """
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="ecom_delivery_slots",
        null=True,
        blank=True
    )
    start = models.DateTimeField()
    end = models.DateTimeField()

    class Meta:
        ordering = ["restaurant", "start"]

    def __str__(self):
        return f"{self.restaurant.name} | {self.start:%Y-%m-%d %H:%M} - {self.end:%H:%M}"


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
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="ecom_cart_items",
        null = True, blank = True

    )
    # lien optionnel vers le plat source
    dish = models.ForeignKey(Dish, on_delete=models.SET_NULL, null=True, blank=True, related_name="cart_items")

    external_item_id = models.CharField(max_length=64, help_text="ID du plat/produit dans un autre service ou l'ID du Dish")
    name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("cart", "restaurant", "external_item_id")

    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.name} x{self.quantity} @ {self.restaurant.name}"


class Order(models.Model):
    PENDING = "PENDING"
    PREPARING = "PREPARING"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

    SERVICE_DELIVERY = "DELIVERY"
    SERVICE_TAKEAWAY = "TAKEAWAY"
    SERVICE_DINE_IN = "DINE_IN"

    STATUS_CHOICES = [
        (PENDING, "En attente"),
        (PREPARING, "En préparation"),
        (OUT_FOR_DELIVERY, "En livraison"),
        (DELIVERED, "Livrée"),
        (CANCELLED, "Annulée"),
    ]
    SERVICE_CHOICES = [
        (SERVICE_DELIVERY, "Livraison"),
        (SERVICE_TAKEAWAY, "À emporter"),
        (SERVICE_DINE_IN, "Sur place"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="ecom_orders",
        null=True, blank=True   # <-- rendre temporairement nullable
        # <- **LE** renommage qui lève le conflit avec pos.Order.restaurant
    )
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    service_type = models.CharField(max_length=16, choices=SERVICE_CHOICES, default=SERVICE_DELIVERY)

    # Adresse de livraison (snapshot) — utilisée si service_type = DELIVERY
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=40, blank=True)

    # Créneau de livraison (propre au restaurant) — requis si DELIVERY
    slot = models.ForeignKey(DeliverySlot, on_delete=models.PROTECT, null=True, blank=True)

    # Totaux
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_points_used = models.IntegerField(default=0)
    discount_euros = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    def __str__(self):
        return f"Order #{self.id} - {self.restaurant.name} - {self.user} - {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="ecom_order_items",
        null=True, blank=True  # <-- rendre temporairement nullable

        # <- safe (au cas où pos aurait aussi order_items)
    )
    dish = models.ForeignKey(Dish, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items")

    external_item_id = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    def save(self, *args, **kwargs):
        self.line_total = self.unit_price * self.quantity
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} x{self.quantity} @ {self.restaurant.name}"
