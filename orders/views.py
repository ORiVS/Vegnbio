# orders/views.py
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, views
from rest_framework.response import Response

from .models import DeliverySlot, Cart, CartItem, Order, OrderItem
from .serializers import (
    DeliverySlotSerializer, CartSerializer, CartAddSerializer, CartRemoveSerializer,
    OrderSerializer, CheckoutSerializer, UpdateStatusSerializer
)

# On a besoin du restaurant lors de l'ajout au panier
from restaurants.models import Restaurant

# Import fidélité
from fidelite.models import LoyaltyProgram, Membership, PointsTransaction


def get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def get_program():
    program, _ = LoyaltyProgram.objects.get_or_create(id=1)
    return program


def get_or_create_membership(user):
    membership, _ = Membership.objects.get_or_create(user=user)
    return membership


class DeliverySlotsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = DeliverySlot.objects.order_by("start")
        return Response(DeliverySlotSerializer(qs, many=True).data)


class CartView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cart = get_or_create_cart(request.user)
        return Response(CartSerializer(cart).data)

    @transaction.atomic
    def post(self, request):
        """
        Ajouter au panier
        body attendu:
        {
          "restaurant_id": <int>,           # requis (nouvelle règle)
          "external_item_id": "DISH-123",
          "name": "Curry de légumes",
          "unit_price": "12.90",
          "quantity": 2
        }
        """
        cart = get_or_create_cart(request.user)

        serializer = CartAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Récupération du restaurant (requis)
        restaurant = get_object_or_404(Restaurant, id=data["restaurant_id"])

        # On distingue un même external_item_id provenant de restaurants différents
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            restaurant=restaurant,
            external_item_id=data["external_item_id"],
            defaults={
                "name": data["name"],
                "unit_price": data["unit_price"],
                "quantity": data.get("quantity", 1),
            }
        )
        if not created:
            # Mise à jour du nom/prix si besoin et incrément de quantité
            item.name = data["name"]
            item.unit_price = data["unit_price"]
            item.quantity += data.get("quantity", 1)
            item.save()

        return Response({"message": "Ajouté au panier"}, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def delete(self, request):
        """
        Retirer un item
        body attendu (legacy) :
        { "external_item_id": "DISH-123" }

        Optionnel (recommandé désormais pour éviter les ambiguïtés) :
        { "external_item_id": "DISH-123", "restaurant_id": 5 }
        """
        cart = get_or_create_cart(request.user)
        serializer = CartRemoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ext_id = serializer.validated_data["external_item_id"]

        # Compat : si restaurant_id est passé, on filtre plus précisément
        restaurant_id = request.data.get("restaurant_id")
        qs = CartItem.objects.filter(cart=cart, external_item_id=ext_id)
        if restaurant_id:
            qs = qs.filter(restaurant_id=restaurant_id)

        deleted, _ = qs.delete()
        if deleted == 0:
            return Response({"message": "Aucun article correspondant trouvé."}, status=404)
        return Response({"message": "Supprimé"})


class CheckoutView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        """
        Valider la commande : transforme le panier en Order + OrderItems
        Peut utiliser des points de fidélité pour réduire le total.

        body:
        {
          "address_line1": "...",
          "address_line2": "",
          "city": "Paris",
          "postal_code": "75010",
          "phone": "06...",
          "slot_id": 3,
          "points_to_use": 100   # optionnel
        }
        """
        cart = get_or_create_cart(request.user)
        if cart.items.count() == 0:
            return Response({"detail": "Panier vide."}, status=status.HTTP_400_BAD_REQUEST)

        # **Sécurité nouvelle** : tous les items doivent être rattachés à un restaurant
        if cart.items.filter(restaurant__isnull=True).exists():
            return Response(
                {
                    "detail": (
                        "Un ou plusieurs articles du panier n’ont pas de restaurant associé. "
                        "Supprimez-les et ré-ajoutez-les (le restaurant est désormais requis)."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        slot = get_object_or_404(DeliverySlot, id=data["slot_id"])

        # Totaux
        subtotal = cart.total()

        # Fidélité: usage points
        program = get_program()
        membership = get_or_create_membership(request.user)
        points_to_use = int(data.get("points_to_use", 0) or 0)
        if points_to_use < 0:
            points_to_use = 0
        if points_to_use > membership.points_balance:
            return Response({"detail": "Points insuffisants."}, status=status.HTTP_400_BAD_REQUEST)

        discount_euros = Decimal(points_to_use) * program.redeem_rate_euro_per_point
        if discount_euros > subtotal:
            # Ajuste le nombre de points au maximum utile
            max_points_needed = int(
                (subtotal / program.redeem_rate_euro_per_point).to_integral_value(rounding="ROUND_FLOOR")
            )
            points_to_use = min(points_to_use, max_points_needed)
            discount_euros = Decimal(points_to_use) * program.redeem_rate_euro_per_point

        total_paid = subtotal - discount_euros

        # Créer la commande (une commande globale — si tu veux un jour
        # faire une commande par restaurant, on la scindera ici)
        order = Order.objects.create(
            user=request.user,
            address_line1=data["address_line1"],
            address_line2=data.get("address_line2", ""),
            city=data["city"],
            postal_code=data["postal_code"],
            phone=data.get("phone", ""),
            slot=slot,
            subtotal=subtotal,
            discount_points_used=points_to_use,
            discount_euros=discount_euros,
            total_paid=total_paid,
        )

        # Items
        for ci in cart.items.select_related("restaurant").all():
            OrderItem.objects.create(
                order=order,
                external_item_id=ci.external_item_id,
                name=ci.name,
                unit_price=ci.unit_price,
                quantity=ci.quantity,
            )
        # Vider panier
        cart.items.all().delete()

        # Débiter points utilisés
        if points_to_use > 0:
            membership.points_balance -= points_to_use
            membership.save()
            PointsTransaction.objects.create(
                membership=membership,
                kind=PointsTransaction.SPEND,
                points=-points_to_use,
                reason=f"Spend at checkout (Order #{order.id})",
                related_order_id=order.id,
            )

        # Créditer points gagnés (sur total payé)
        if total_paid > 0:
            earned = int((total_paid * program.earn_rate_per_euro).to_integral_value(rounding="ROUND_FLOOR"))
            if earned > 0:
                membership.points_balance += earned
                membership.save()
                PointsTransaction.objects.create(
                    membership=membership,
                    kind=PointsTransaction.EARN,
                    points=earned,
                    reason=f"Earn on purchase (Order #{order.id})",
                    related_order_id=order.id,
                )

        return Response({"message": "Commande créée", "order": OrderSerializer(order).data},
                        status=status.HTTP_201_CREATED)


class MyOrdersView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = Order.objects.filter(user=request.user).order_by("-created_at")
        return Response(OrderSerializer(qs, many=True).data)


class OrderStatusView(views.APIView):
    """
    Récupérer statut (client) ou mettre à jour (restaurateur/admin).
    Pour la mise à jour, protège avec une permission custom si tu as un rôle RESTAURATEUR/ADMIN.
    Ici, on ouvre un PATCH simple (à sécuriser selon ton système de rôles).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        order = get_object_or_404(Order, pk=pk, user=request.user)
        return Response({"id": order.id, "status": order.status})

    @transaction.atomic
    def patch(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        serializer = UpdateStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order.status = serializer.validated_data["status"]
        order.save()
        return Response({"message": "Statut mis à jour", "id": order.id, "status": order.status})
