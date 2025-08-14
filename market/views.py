from datetime import datetime
from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import SupplierOffer, OfferReview, OfferReport
from .serializers import SupplierOfferSerializer, OfferReviewSerializer, OfferReportSerializer
from .permissions import IsSupplier, IsRestaurateur, IsAdminVegNBio
from menu.models import Product, Allergen  # import pour import_to_product

class SupplierOfferViewSet(viewsets.ModelViewSet):
    queryset = SupplierOffer.objects.select_related("supplier").prefetch_related("allergens","reviews").all()
    serializer_class = SupplierOfferSerializer

    def get_permissions(self):
        if self.action in ["create","update","partial_update","destroy","publish","unlist","draft"]:
            return [permissions.IsAuthenticated(), IsSupplier()]
        # lecture: restaurateur (principal) + admin + (option) public
        if self.action in ["list","retrieve","compare"]:
            return [permissions.AllowAny()]
        if self.action in ["import_to_product"]:
            return [permissions.IsAuthenticated(), IsRestaurateur()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params

        # visibilité: on affiche par défaut seulement PUBLISHED (sauf si supplier voit ses brouillons)
        if not (self.request.user.is_authenticated and self.request.user.role == "FOURNISSEUR"):
            qs = qs.filter(status="PUBLISHED")
        else:
            # un fournisseur voit ses propres offres (tous statuts) + offres publiques
            qs = qs.filter(Q(status="PUBLISHED") | Q(supplier=self.request.user))

        # recherche & filtres
        if p.get("q"):
            q = p["q"]
            qs = qs.filter(Q(product_name__icontains=q) | Q(producer_name__icontains=q) | Q(description__icontains=q))
        if p.get("is_bio") in ["true","false"]:
            qs = qs.filter(is_bio=(p["is_bio"]=="true"))
        if p.get("region"):
            qs = qs.filter(region__iexact=p["region"])
        if p.get("allergen"):
            qs = qs.filter(allergens__code__in=p["allergen"].split(",")).distinct()
        if p.get("exclude_allergens"):
            qs = qs.exclude(allergens__code__in=p["exclude_allergens"].split(",")).distinct()
        if p.get("available_on"):
            d = parse_date(p["available_on"])
            if d:
                qs = [o for o in qs if o.is_available_on(d)]
        # tri
        if p.get("sort") == "price":
            qs = qs.order_by("price")
        elif p.get("sort") == "-price":
            qs = qs.order_by("-price")
        return qs

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        offer = self.get_object()
        if offer.supplier != request.user:
            return Response({"detail":"Interdit"}, status=403)
        offer.status = "PUBLISHED"
        offer.save()
        return Response({"status":"published"})

    @action(detail=True, methods=["post"])
    def unlist(self, request, pk=None):
        offer = self.get_object()
        if offer.supplier != request.user:
            return Response({"detail":"Interdit"}, status=403)
        offer.status = "UNLISTED"
        offer.save()
        return Response({"status":"unlisted"})

    @action(detail=True, methods=["post"])
    def draft(self, request, pk=None):
        offer = self.get_object()
        if offer.supplier != request.user:
            return Response({"detail":"Interdit"}, status=403)
        offer.status = "DRAFT"
        offer.save()
        return Response({"status":"draft"})

    @action(detail=False, methods=["get"])
    def compare(self, request):
        ids = request.query_params.get("ids")
        if not ids:
            return Response({"detail":"ids=1,2,3 requis"}, status=400)
        ids = [int(i) for i in ids.split(",") if i.isdigit()]
        qs = self.get_queryset().filter(id__in=ids)
        data = self.get_serializer(qs, many=True).data
        return Response(data)

    @action(detail=True, methods=["post"])
    def import_to_product(self, request, pk=None):
        """Restaurateur: créer un Product (module menu) depuis une offre"""
        offer = self.get_object()
        # créer Product
        prod = Product.objects.create(
            name=offer.product_name,
            is_bio=offer.is_bio,
            producer_name=offer.producer_name or "",
            region=offer.region,
            is_vegetarian=True,
        )
        if offer.allergens.exists():
            prod.allergens.set(list(offer.allergens.all()))
        return Response({"status":"imported", "product_id": prod.id})


class OfferReviewViewSet(viewsets.ModelViewSet):
    queryset = OfferReview.objects.select_related("offer","author").all()
    serializer_class = OfferReviewSerializer

    def get_permissions(self):
        if self.action in ["create"]:
            # Uniquement restaurateurs (ou admin) laissent des avis
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        if self.request.user.role not in ["RESTAURATEUR", "ADMIN"]:
            raise PermissionError("Seuls restaurateurs/admin peuvent noter.")
        serializer.save()


class OfferReportViewSet(viewsets.ModelViewSet):
    queryset = OfferReport.objects.select_related("offer","reporter").all()
    serializer_class = OfferReportSerializer

    def get_permissions(self):
        if self.action in ["create"]:
            return [permissions.IsAuthenticated()]
        if self.action in ["moderate"]:
            return [permissions.IsAuthenticated(), IsAdminVegNBio()]
        return [permissions.AllowAny()]

    @action(detail=True, methods=["post"])
    def moderate(self, request, pk=None):
        report = self.get_object()
        action = request.data.get("action")  # REVIEWED / ACTION_TAKEN
        if action not in ["REVIEWED","ACTION_TAKEN"]:
            return Response({"detail":"action invalide"}, status=400)
        report.status = action
        report.save()
        return Response({"status": report.status})
