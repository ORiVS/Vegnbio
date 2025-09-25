from decimal import Decimal
from django.db import transaction
from rest_framework import serializers
from .models import SupplierOrder, SupplierOrderItem
from market.models import SupplierOffer

class SupplierOrderItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierOrderItem
        fields = ["offer", "qty_requested"]

    def validate(self, data):
        offer = data["offer"]
        if offer.status != "PUBLISHED":
            raise serializers.ValidationError("Impossible de commander une offre non publiée.")
        if offer.stock_qty <= 0:
            raise serializers.ValidationError("Stock indisponible.")
        return data


class SupplierOrderCreateSerializer(serializers.ModelSerializer):
    items = SupplierOrderItemCreateSerializer(many=True)

    class Meta:
        model = SupplierOrder
        fields = ["supplier", "note", "items"]

    def create(self, validated_data):
        user = self.context["request"].user
        items_data = validated_data.pop("items")
        order = SupplierOrder.objects.create(restaurateur=user, **validated_data)
        for it in items_data:
            offer = it["offer"]
            SupplierOrderItem.objects.create(
                order=order,
                offer=offer,
                qty_requested=it["qty_requested"],
                unit_price=offer.price
            )
        return order


class SupplierOrderItemReadSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="offer.product_name", read_only=True)
    unit = serializers.CharField(source="offer.unit", read_only=True)

    class Meta:
        model = SupplierOrderItem
        fields = ["id","offer","product_name","unit","qty_requested","qty_confirmed","unit_price"]


class SupplierOrderReadSerializer(serializers.ModelSerializer):
    items = SupplierOrderItemReadSerializer(many=True, read_only=True)
    class Meta:
        model = SupplierOrder
        fields = ["id","restaurateur","supplier","status","created_at","confirmed_at","note","items"]


class SupplierOrderSupplierReviewSerializer(serializers.Serializer):
    items = serializers.ListField(
        child=serializers.DictField(child=serializers.DecimalField(max_digits=12, decimal_places=2)),
        allow_empty=False
    )
    # format attendu:
    # {
    #   "items": [
    #     {"id": 10, "qty_confirmed": 4.5},
    #     {"id": 11, "qty_confirmed": 0}
    #   ]
    # }

    def validate(self, data):
        # vérifier existence des items et non dépassement du stock
        order: SupplierOrder = self.context["order"]
        items_input = data["items"]
        items_map = {int(i["id"]): i["qty_confirmed"] for i in items_input}
        db_items = {itm.id: itm for itm in order.items.select_related("offer")}
        for item_id, qty_conf in items_map.items():
            if item_id not in db_items:
                raise serializers.ValidationError(f"Item {item_id} introuvable dans la commande.")
            if qty_conf < 0:
                raise serializers.ValidationError("Quantité confirmée ne peut pas être négative.")
            offer = db_items[item_id].offer
            if qty_conf > offer.stock_qty:
                raise serializers.ValidationError(
                    f"Quantité confirmée ({qty_conf}) dépasse le stock dispo ({offer.stock_qty}) pour l'offre {offer.id}."
                )
        return data

    def save(self, **kwargs):
        order: SupplierOrder = self.context["order"]
        supplier = self.context["request"].user
        if order.supplier != supplier:
            raise serializers.ValidationError("Seul le producteur concerné peut valider cette commande.")

        items_input = self.validated_data["items"]
        items_map = {int(i["id"]): i["qty_confirmed"] for i in items_input}
        partial = False
        all_zero = True

        with transaction.atomic():
            for item in order.items.select_related("offer").select_for_update():
                qty_conf = items_map.get(item.id, None)
                if qty_conf is None:
                    continue
                item.qty_confirmed = qty_conf
                item.save(update_fields=["qty_confirmed"])
                if qty_conf > 0:
                    all_zero = False
                    if qty_conf < item.qty_requested:
                        partial = True
                    # décrémentation du stock
                    offer = item.offer
                    offer.stock_qty = offer.stock_qty - qty_conf
                    offer.save(update_fields=["stock_qty"])

            if all_zero:
                order.status = "REJECTED"
            elif partial:
                order.status = "PARTIALLY_CONFIRMED"
            else:
                order.status = "CONFIRMED"
            order.save(update_fields=["status"])
        return order
