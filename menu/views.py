from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.dateparse import parse_date
from django.db.models import Q

from .models import Allergen, Product, Dish, DishAvailability, Menu
from .serializers import (
    AllergenSerializer, ProductSerializer, DishSerializer,
    DishAvailabilitySerializer, MenuSerializer
)
from restaurants.permissions import IsRestaurateur

class PublicReadMixin:
    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy", "publish", "unpublish"]:
            return [permissions.IsAuthenticated(), IsRestaurateur()]
        return [permissions.AllowAny()]

class AllergenViewSet(PublicReadMixin, viewsets.ModelViewSet):
    queryset = Allergen.objects.all()
    serializer_class = AllergenSerializer

class ProductViewSet(PublicReadMixin, viewsets.ModelViewSet):
    queryset = Product.objects.prefetch_related("allergens").all()
    serializer_class = ProductSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("is_bio") in ["true", "false"]:
            qs = qs.filter(is_bio=(p["is_bio"] == "true"))
        if p.get("region"):
            qs = qs.filter(region__iexact=p["region"])
        if p.get("allergen"):
            qs = qs.filter(allergens__code__in=p.get("allergen").split(",")).distinct()
        return qs

class DishViewSet(PublicReadMixin, viewsets.ModelViewSet):
    queryset = Dish.objects.prefetch_related("products__allergens", "extra_allergens").all()
    serializer_class = DishSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("is_active") in ["true", "false"]:
            qs = qs.filter(is_active=(p["is_active"] == "true"))
        if p.get("is_vegan") in ["true", "false"]:
            qs = qs.filter(is_vegan=(p["is_vegan"] == "true"))
        if p.get("exclude_allergens"):
            excl = p["exclude_allergens"].split(",")
            qs = qs.exclude(
                Q(products__allergens__code__in=excl) | Q(extra_allergens__code__in=excl)
            ).distinct()
        return qs

    @action(detail=True, methods=["patch"])
    def deactivate(self, request, pk=None):
        dish = self.get_object()
        dish.is_active = False
        dish.save()
        return Response({"status": "dish deactivated"})

    @action(detail=True, methods=["patch"])
    def activate(self, request, pk=None):
        dish = self.get_object()
        dish.is_active = True
        dish.save()
        return Response({"status": "dish activated"})

class DishAvailabilityViewSet(PublicReadMixin, viewsets.ModelViewSet):
    queryset = DishAvailability.objects.select_related("dish", "restaurant").all()
    serializer_class = DishAvailabilitySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("restaurant"):
            qs = qs.filter(restaurant_id=p["restaurant"])
        if p.get("date"):
            qs = qs.filter(date=p["date"])
        return qs

class MenuViewSet(PublicReadMixin, viewsets.ModelViewSet):
    queryset = Menu.objects.prefetch_related("items__dish", "restaurants").all()
    serializer_class = MenuSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        include_unpublished = p.get("include_unpublished") == "true"
        if not include_unpublished:
            qs = qs.filter(is_published=True)
        if p.get("restaurant"):
            qs = qs.filter(restaurants__id=p["restaurant"])
        if p.get("date"):
            d = parse_date(p["date"])
            if d:
                qs = qs.filter(start_date__lte=d, end_date__gte=d)
        return qs.distinct()

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        menu = self.get_object()
        if not menu.items.exists():
            return Response({"detail": "Impossible de publier un menu sans items."}, status=400)
        menu.is_published = True
        menu.save()
        return Response({"status": "menu published"})

    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        menu = self.get_object()
        menu.is_published = False
        menu.save()
        return Response({"status": "menu unpublished"})
