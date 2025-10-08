from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import SupplierOrder, SupplierOrderItem
from .serializers import (
    SupplierOrderCreateSerializer,
    SupplierOrderReadSerializer,
    SupplierOrderSupplierReviewSerializer,
)
from restaurants.permissions import IsRestaurateur, IsSupplier


class SupplierOrderViewSet(viewsets.GenericViewSet):
    """
    Endpoints principaux :
    - POST   /api/purchasing/orders/                 (create_order) [restaurateur]
    - GET    /api/purchasing/orders/my_restaurant/   (mes commandes) [restaurateur]
    - GET    /api/purchasing/orders/supplier_inbox/  (boîte de réception) [fournisseur]
    - POST   /api/purchasing/orders/{id}/review/     (validation fournisseur) [fournisseur]
    - GET    /api/purchasing/orders/{id}/            (lecture)
    """
    queryset = SupplierOrder.objects.select_related("restaurateur", "supplier").prefetch_related("items")
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return SupplierOrderCreateSerializer
        return SupplierOrderReadSerializer

    # ---------- RESTAURATEUR : créer une commande ----------
    def create(self, request, *args, **kwargs):
        """
        Body:
        {
          "supplier": <id>,
          "note": "...",
          "items": [{ "offer": <id>, "qty_requested": <decimal> }, ...]
        }
        """
        self.permission_classes = [permissions.IsAuthenticated, IsRestaurateur]
        self.check_permissions(request)

        ser = SupplierOrderCreateSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        order = ser.save()
        return Response(SupplierOrderReadSerializer(order).data, status=status.HTTP_201_CREATED)

    # ---------- RESTAURATEUR : mes commandes ----------
    @action(detail=False, methods=["get"], url_path="my_restaurant", permission_classes=[permissions.IsAuthenticated, IsRestaurateur])
    def my_restaurant_orders(self, request):
        qs = self.get_queryset().filter(restaurateur=request.user).order_by("-created_at")
        return Response(SupplierOrderReadSerializer(qs, many=True).data)

    # ---------- FOURNISSEUR : boîte de réception ----------
    @action(detail=False, methods=["get"], url_path="supplier_inbox", permission_classes=[permissions.IsAuthenticated, IsSupplier])
    def supplier_inbox(self, request):
        qs = self.get_queryset().filter(supplier=request.user, status__in=["PENDING_SUPPLIER"]).order_by("-created_at")
        return Response(SupplierOrderReadSerializer(qs, many=True).data)

    # ---------- FOURNISSEUR : review / validation ----------
    @action(detail=True, methods=["post"], url_path="review", permission_classes=[permissions.IsAuthenticated, IsSupplier])
    def supplier_review(self, request, pk=None):
        order = get_object_or_404(self.get_queryset(), pk=pk)
        if order.supplier != request.user:
            return Response({"detail": "Accès interdit."}, status=403)

        ser = SupplierOrderSupplierReviewSerializer(data=request.data, context={"order": order, "request": request})
        ser.is_valid(raise_exception=True)
        order = ser.save()
        return Response(SupplierOrderReadSerializer(order).data)

    # ---------- lecture simple ----------
    def retrieve(self, request, pk=None):
        order = get_object_or_404(self.get_queryset(), pk=pk)
        if request.user not in [order.restaurateur, order.supplier] and getattr(request.user, "role", None) != "ADMIN":
            return Response({"detail": "Accès interdit."}, status=403)
        return Response(SupplierOrderReadSerializer(order).data)
