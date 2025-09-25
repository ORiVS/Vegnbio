from rest_framework import serializers
from .models import DeliverySlot, Cart, CartItem, Order, OrderItem

class DeliverySlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliverySlot
        fields = ["id", "start", "end"]


class CartItemSerializer(serializers.ModelSerializer):
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ["id", "external_item_id", "name", "unit_price", "quantity", "line_total"]

    def get_line_total(self, obj):
        return str(obj.line_total())


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["user", "items", "total"]

    def get_total(self, obj):
        return str(obj.total())


class CartAddSerializer(serializers.Serializer):
    restaurant_id = serializers.IntegerField()
    external_item_id = serializers.CharField()
    name = serializers.CharField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField(min_value=1, default=1)


class CartRemoveSerializer(serializers.Serializer):
    external_item_id = serializers.CharField()


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["external_item_id", "name", "unit_price", "quantity", "line_total"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "status", "created_at",
            "address_line1", "address_line2", "city", "postal_code", "phone",
            "slot", "subtotal", "discount_points_used", "discount_euros", "total_paid",
            "items"
        ]


class CheckoutSerializer(serializers.Serializer):
    # Adresse
    address_line1 = serializers.CharField()
    address_line2 = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField()
    postal_code = serializers.CharField()
    phone = serializers.CharField(required=False, allow_blank=True)
    # Créneau
    slot_id = serializers.IntegerField()
    # Points utilisés (optionnel)
    points_to_use = serializers.IntegerField(required=False, default=0, min_value=0)


class UpdateStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES)
