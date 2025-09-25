from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.mail import send_mail

from .models import SupplierOrder
from .serializers import (
    SupplierOrderCreateSerializer,
    SupplierOrderReadSerializer,
    SupplierOrderSupplierReviewSerializer,
)
from market.permissions import IsRestaurateur, IsSupplier

class SupplierOrderViewSet(viewsets.ModelViewSet):
    queryset = SupplierOrder.objects.select_related("restaurateur","supplier").prefetch_related("items__offer").all()

    def get_permissions(self):
        if self.action in ["create", "my_restaurant_orders"]:
            return [permissions.IsAuthenticated(), IsRestaurateur()]
        if self.action in ["supplier_inbox", "supplier_review"]:
            return [permissions.IsAuthenticated(), IsSupplier()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "create":
            return SupplierOrderCreateSerializer
        elif self.action in ["list", "retrieve", "my_restaurant_orders", "supplier_inbox"]:
            return SupplierOrderReadSerializer
        elif self.action == "supplier_review":
            return SupplierOrderSupplierReviewSerializer
        return SupplierOrderReadSerializer

    def list(self, request, *args, **kwargs):
        # admin only: tout voir
        if getattr(request.user, "role", None) != "ADMIN":
            return Response({"detail": "Réservé à l'admin."}, status=403)
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        order = serializer.save()
        send_mail(
            subject="Nouvelle commande à valider",
            message=f"Vous avez reçu une commande #{order.id} à confirmer.",
            from_email=None,
            recipient_list=[order.supplier.email],
            fail_silently=True,
        )

    @action(detail=False, methods=["get"])
    def my_restaurant_orders(self, request):
        qs = self.get_queryset().filter(restaurateur=request.user)
        ser = SupplierOrderReadSerializer(qs, many=True)
        return Response(ser.data)

    @action(detail=False, methods=["get"])
    def supplier_inbox(self, request):
        qs = self.get_queryset().filter(supplier=request.user)
        ser = SupplierOrderReadSerializer(qs, many=True)
        return Response(ser.data)

    @action(detail=True, methods=["post"])
    def supplier_review(self, request, pk=None):
        order = self.get_object()
        ser = SupplierOrderSupplierReviewSerializer(data=request.data, context={"order": order, "request": request})
        ser.is_valid(raise_exception=True)
        order = ser.save()
        return Response(SupplierOrderReadSerializer(order).data, status=200)
