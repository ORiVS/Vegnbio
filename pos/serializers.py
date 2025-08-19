from decimal import Decimal
from rest_framework import serializers
from .models import Order, OrderItem, Payment

class OrderItemSerializer(serializers.ModelSerializer):
    dish_name = serializers.CharField(source="dish.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "dish", "dish_name", "custom_name", "unit_price", "quantity"]

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id","restaurant","restaurant_name","status","tax_rate",
            "discount_amount","discount_percent",
            "subtotal","tax_total","total_due","paid_amount","change_due",
            "note","opened_at","closed_at","items",
        ]
        read_only_fields = ["subtotal","tax_total","total_due","paid_amount","change_due","opened_at","closed_at","status"]

    def validate(self, data):
        if data.get("discount_percent", Decimal("0")) < 0 or data.get("discount_percent", Decimal("0")) > 100:
            raise serializers.ValidationError("discount_percent doit être entre 0 et 100.")
        return data

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id","order","method","amount","received_at","note"]
        read_only_fields = ["received_at"]
