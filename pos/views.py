# pos/views.py
from decimal import Decimal
from django.db import transaction
from django.utils.dateparse import parse_date
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from restaurants.permissions import IsRestaurateur, IsAdminVegNBio
from .models import Order, OrderItem, Payment
from .serializers import OrderSerializer, OrderItemSerializer, PaymentSerializer

def _is_owner(user, order: Order) -> bool:
    return getattr(user, "role", None) in ["RESTAURATEUR","ADMIN"] and (
        order.restaurant.owner == user or getattr(user, "role", None) == "ADMIN"
    )

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.select_related("restaurant","cashier").prefetch_related("items","payments").all()
    serializer_class = OrderSerializer

    def get_permissions(self):
        if self.action in [
            "create","update","partial_update","destroy",
            "add_item","update_item","remove_item",
            "apply_discount","hold","reopen","checkout","cancel",
            "ticket","summary"
        ]:
            Combined = IsRestaurateur | IsAdminVegNBio
            return [permissions.IsAuthenticated(), Combined()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        # filtre par restaurant/date
        p = self.request.query_params
        if p.get("restaurant"):
            qs = qs.filter(restaurant_id=p["restaurant"])
        if p.get("date"):
            d = parse_date(p["date"])
            if d:
                qs = qs.filter(opened_at__date=d)
        return qs

    def perform_create(self, serializer):
        order = serializer.save(cashier=self.request.user)
        order.recalc_totals()
        order.save(update_fields=["subtotal","tax_total","total_due","change_due"])

    def perform_update(self, serializer):
        order = self.get_object()
        if not _is_owner(self.request.user, order):
            return Response({"detail":"Accès interdit."}, status=403)
        order.ensure_mutable()
        order = serializer.save()
        order.recalc_totals()
        order.save(update_fields=["subtotal","tax_total","total_due","change_due"])

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        if not _is_owner(request.user, order):
            return Response({"detail":"Accès interdit."}, status=403)
        if order.status not in ["OPEN","HOLD"]:
            return Response({"detail":"Impossible de supprimer: commande non modifiable."}, status=400)
        return super().destroy(request, *args, **kwargs)

    # ------- Lignes -------
    @action(detail=True, methods=["post"])
    def add_item(self, request, pk=None):
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail": "Accès interdit."}, status=403)
        order.ensure_mutable()

        ser = OrderItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(order=order)

        # 🔧 rafraîchir l'instance avant recalc (pour être 100% sûr)
        order.refresh_from_db()

        order.recalc_totals()
        order.save(update_fields=["subtotal", "tax_total", "total_due", "change_due"])
        return Response(OrderSerializer(order).data, status=201)

    # update_item : PATCH / PUT sur .../items/<id>/update/
    @action(detail=True, methods=["patch", "put"], url_path=r"items/(?P<item_id>\d+)/update", url_name="update_item")
    def update_item(self, request, pk=None, item_id=None):
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail": "Accès interdit."}, status=403)
        order.ensure_mutable()

        try:
            item = order.items.get(pk=item_id)
        except OrderItem.DoesNotExist:
            return Response({"detail": "Ligne introuvable."}, status=404)

        ser = OrderItemSerializer(item, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()

        order.refresh_from_db()  # 🔧
        order.recalc_totals()
        order.save(update_fields=["subtotal", "tax_total", "total_due", "change_due"])
        return Response(OrderSerializer(order).data)

    # remove_item : DELETE sur .../items/<id>/remove/
    @action(detail=True, methods=["delete"], url_path=r"items/(?P<item_id>\d+)/remove", url_name="remove_item")
    def remove_item(self, request, pk=None, item_id=None):
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail": "Accès interdit."}, status=403)
        order.ensure_mutable()

        deleted, _ = order.items.filter(pk=item_id).delete()
        if not deleted:
            return Response({"detail": "Ligne introuvable."}, status=404)

        order.refresh_from_db()  # 🔧
        order.recalc_totals()
        order.save(update_fields=["subtotal", "tax_total", "total_due", "change_due"])
        return Response(OrderSerializer(order).data)


    # ------- Remise / statut -------
    @action(detail=True, methods=["post"])
    def apply_discount(self, request, pk=None):
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail":"Accès interdit."}, status=403)
        order.ensure_mutable()
        amount = Decimal(str(request.data.get("discount_amount", "0") or "0"))
        percent = Decimal(str(request.data.get("discount_percent", "0") or "0"))
        if percent < 0 or percent > 100:
            return Response({"detail":"discount_percent doit être 0..100."}, status=400)
        order.discount_amount = amount
        order.discount_percent = percent
        order.recalc_totals(); order.save(update_fields=["discount_amount","discount_percent","subtotal","tax_total","total_due","change_due"])
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def hold(self, request, pk=None):
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail":"Accès interdit."}, status=403)
        order.ensure_mutable()
        order.status = "HOLD"
        order.save(update_fields=["status"])
        return Response({"status":"HOLD"})

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail":"Accès interdit."}, status=403)
        if order.status not in ["HOLD","CANCELLED"]:
            return Response({"detail":"Seules les commandes en HOLD/ANNULÉE peuvent être rouvertes."}, status=400)
        order.status = "OPEN"
        order.save(update_fields=["status"])
        return Response({"status":"OPEN"})

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail":"Accès interdit."}, status=403)
        if order.status in ["PAID","REFUNDED"]:
            return Response({"detail":"Commande payée: annulation impossible (faire un remboursement)."}, status=400)
        order.status = "CANCELLED"
        order.save(update_fields=["status"])
        return Response({"status":"CANCELLED"})

    # ------- Encaissement -------
    @action(detail=True, methods=["post"])
    def checkout(self, request, pk=None):
        """
        Enregistre un paiement et clôt si total atteint.
        Body: { "method": "CASH|CARD|ONLINE", "amount": 25.00, "note": "..." }
        """
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail":"Accès interdit."}, status=403)
        if order.status in ["CANCELLED","REFUNDED"]:
            return Response({"detail":"Commande annulée/remboursée."}, status=400)

        ser = PaymentSerializer(data={**request.data, "order": order.id})
        ser.is_valid(raise_exception=True)

        with transaction.atomic():
            payment = ser.save()
            order.paid_amount = (order.paid_amount + payment.amount).quantize(Decimal("0.01"))
            order.recalc_totals()
            order.close_if_paid()
            order.save(update_fields=["paid_amount","subtotal","tax_total","total_due","change_due","status","closed_at"])

        return Response({"status": order.status,
                         "paid_amount": str(order.paid_amount),
                         "change_due": str(order.change_due)})

    # ------- Ticket / Résumé -------
    @action(detail=True, methods=["get"])
    def ticket(self, request, pk=None):
        order = self.get_object()
        if not _is_owner(request.user, order): return Response({"detail":"Accès interdit."}, status=403)
        return Response({
            "order_id": order.id,
            "restaurant": order.restaurant.name,
            "opened_at": order.opened_at,
            "closed_at": order.closed_at,
            "items": [
                {
                    "label": it.custom_name or (it.dish.name if it.dish else ""),
                    "qty": it.quantity,
                    "unit_price": str(it.unit_price),
                    "line_total": str(it.unit_price * it.quantity)
                } for it in order.items.all()
            ],
            "subtotal": str(order.subtotal),
            "discount_amount": str(order.discount_amount),
            "discount_percent": str(order.discount_percent),
            "tax_rate": str(order.tax_rate),
            "tax_total": str(order.tax_total),
            "total_due": str(order.total_due),
            "paid_amount": str(order.paid_amount),
            "change_due": str(order.change_due),
            "status": order.status
        })

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """
        /api/pos/orders/summary/?restaurant=1&date=2025-10-10
        """
        qs = self.get_queryset()
        total = sum((o.total_due for o in qs if o.status in ["PAID","REFUNDED"]), Decimal("0.00"))
        count = qs.count()
        return Response({"count": count, "turnover": str(total)})
