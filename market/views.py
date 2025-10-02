from datetime import date
from django.db import transaction
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.core.mail import send_mail

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .models import SupplierOffer, OfferReview, OfferReport, OfferComment
from .serializers import SupplierOfferSerializer, OfferReviewSerializer, OfferReportSerializer, OfferCommentSerializer
from .permissions import IsSupplier, IsRestaurateur, IsAdminVegNBio
from menu.models import Product

class SupplierOfferViewSet(viewsets.ModelViewSet):
    queryset = SupplierOffer.objects.select_related("supplier").prefetch_related("allergens","reviews").all()
    serializer_class = SupplierOfferSerializer

    def get_permissions(self):
        if self.action in ["create","update","partial_update","destroy","publish","unlist","draft"]:
            return [permissions.IsAuthenticated(), IsSupplier()]
        if self.action in ["list","retrieve","compare"]:
            return [permissions.AllowAny()]
        if self.action in ["import_to_product"]:
            return [permissions.IsAuthenticated(), IsRestaurateur()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params

        if not (self.request.user.is_authenticated and getattr(self.request.user, "role", None) == "FOURNISSEUR"):
            qs = qs.filter(status="PUBLISHED")
        else:
            qs = qs.filter(Q(status="PUBLISHED") | Q(supplier=self.request.user))

        # recherche / filtres
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

        # filtre disponibilité par date en conservant un queryset
        if p.get("available_on"):
            d = parse_date(p["available_on"])
            if d:
                qs = qs.filter(
                    Q(available_from__isnull=True) | Q(available_from__lte=d),
                    Q(available_to__isnull=True)   | Q(available_to__gte=d),
                    stock_qty__gt=0
                )

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
        offer.full_clean()
        offer.save()
        return Response({"status":"published"})

    @action(detail=True, methods=["post"])
    def unlist(self, request, pk=None):
        offer = self.get_object()
        if offer.supplier != request.user:
            return Response({"detail":"Interdit"}, status=403)
        offer.status = "UNLISTED"
        offer.save(update_fields=["status"])
        return Response({"status":"unlisted"})

    @action(detail=True, methods=["post"])
    def draft(self, request, pk=None):
        offer = self.get_object()
        if offer.supplier != request.user:
            return Response({"detail":"Interdit"}, status=403)
        offer.status = "DRAFT"
        offer.save(update_fields=["status"])
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
        offer = self.get_object()
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

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def flag(self, request, pk=None):
        offer = self.get_object()
        reason = request.data.get("reason")
        details = request.data.get("details", "")
        if not reason:
            return Response({"detail": "reason requis."}, status=400)
        if offer.supplier == request.user:
            return Response({"detail": "Impossible de signaler votre propre offre."}, status=400)

        OfferReport.objects.create(offer=offer, reporter=request.user, reason=reason, details=details)
        offer.status = "FLAGGED"
        offer.save(update_fields=["status"])

        send_mail(
            subject="Offre signalée",
            message=f"Votre offre '{offer.product_name}' a été signalée pour: {reason}.",
            from_email=None,  # DEFAULT_FROM_EMAIL
            recipient_list=[offer.supplier.email],
            fail_silently=True,
        )
        return Response({"status": "flagged"}, status=201)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsAdminVegNBio()])
    def moderate_status(self, request, pk=None):
        offer = self.get_object()
        new_status = request.data.get("status")
        if new_status not in ["PUBLISHED", "UNLISTED", "DRAFT"]:
            return Response({"detail": "status invalide."}, status=400)
        offer.status = new_status
        offer.save(update_fields=["status"])
        return Response({"status": offer.status})


class OfferReviewViewSet(viewsets.ModelViewSet):
    queryset = OfferReview.objects.select_related("offer","author").all()
    serializer_class = OfferReviewSerializer

    def get_permissions(self):
        if self.action in ["create"]:
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]


    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        offer_id = p.get("offer")
        rating = p.get("rating")

        if offer_id and offer_id.isdigit():
            qs = qs.filter(offer_id=int(offer_id))
        if rating and rating.isdigit():
            qs = qs.filter(rating=int(rating))

        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        role = getattr(self.request.user, "role", None)
        if role not in ["RESTAURATEUR", "ADMIN"]:
            raise PermissionDenied("Seuls restaurateurs/admin peuvent noter.")
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


class IsAuthorOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        role = getattr(request.user, "role", None)
        return obj.author == request.user or role == "ADMIN"


class OfferCommentViewSet(viewsets.ModelViewSet):
    queryset = OfferComment.objects.select_related("offer", "author").all()
    serializer_class = OfferCommentSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        if not (self.request.user.is_authenticated and getattr(self.request.user, "role", None) == "ADMIN"):
            qs = qs.filter(is_public=True)
        offer_id = self.request.query_params.get("offer")
        if offer_id:
            qs = qs.filter(offer_id=offer_id)
        return qs

    def perform_update(self, serializer):
        obj = self.get_object()
        role = getattr(self.request.user, "role", None)
        if not (obj.author == self.request.user or role == "ADMIN"):
            raise PermissionDenied("Accès interdit.")
        serializer.save(is_edited=True)

    def perform_destroy(self, instance):
        role = getattr(self.request.user, "role", None)
        if not (instance.author == self.request.user or role == "ADMIN"):
            raise PermissionDenied("Accès interdit.")
        return super().perform_destroy(instance)
