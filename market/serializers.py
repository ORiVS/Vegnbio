from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from rest_framework import serializers

from .models import SupplierOffer, OfferReview, OfferReport, OfferComment, REGIONS_ALLOWED
from menu.models import Allergen

class SupplierOfferSerializer(serializers.ModelSerializer):
    supplier = serializers.HiddenField(default=serializers.CurrentUserDefault())
    # ⬇️ expose l'id du fournisseur pour le front
    supplier_id = serializers.IntegerField(source="supplier.id", read_only=True)
    allergens = serializers.PrimaryKeyRelatedField(queryset=Allergen.objects.all(), many=True, required=False)
    avg_rating = serializers.SerializerMethodField()

    class Meta:
        model = SupplierOffer
        fields = [
            "id", "supplier", "supplier_id",
            "product_name", "description", "is_bio", "producer_name", "region", "allergens",
            "unit", "price", "min_order_qty", "stock_qty",
            "available_from", "available_to",
            "status", "avg_rating", "created_at",
        ]
        read_only_fields = ["status", "avg_rating", "created_at", "supplier_id"]

    def get_avg_rating(self, obj):
        ratings = list(obj.reviews.all().values_list("rating", flat=True))
        return round(sum(ratings)/len(ratings), 2) if ratings else None

    def validate(self, data):
        user = self.context["request"].user

        # rôle
        if getattr(user, "role", None) != "FOURNISSEUR":
            raise serializers.ValidationError("Seuls les fournisseurs peuvent créer/éditer des offres.")

        # producteur IDF (via profil)
        prof = getattr(user, "profile", None)
        if not prof or prof.region not in REGIONS_ALLOWED:
            raise serializers.ValidationError("Le producteur doit être domicilié en Île-de-France.")

        # région du produit IDF
        if data.get("region") and data["region"] not in REGIONS_ALLOWED:
            raise serializers.ValidationError("Région du produit non autorisée. Exigence: Île-de-France.")

        # label bio obligatoire
        if "is_bio" in data and data["is_bio"] is False:
            raise serializers.ValidationError("Seuls des produits biologiques (is_bio=true) sont autorisés.")

        # prix / quantités
        if data.get("price", 0) < 0 or data.get("min_order_qty", 0) <= 0:
            raise serializers.ValidationError("Prix et quantité minimale doivent être positifs.")

        # limite hebdo (création uniquement)
        request = self.context.get("request")
        is_create = request and request.method == "POST"
        if is_create:
            limit = getattr(settings, "SUPPLIER_WEEKLY_OFFER_LIMIT", 5)
            since = timezone.now() - timedelta(days=7)
            count = SupplierOffer.objects.filter(supplier=user, created_at__gte=since).count()
            if count >= limit:
                raise serializers.ValidationError(f"Limite atteinte: {limit} nouvelles offres autorisées sur 7 jours.")

        return data


class OfferReviewSerializer(serializers.ModelSerializer):
    author = serializers.HiddenField(default=serializers.CurrentUserDefault())
    class Meta:
        model = OfferReview
        fields = ["id","offer","author","rating","comment","created_at"]
        read_only_fields = ["created_at"]

    def validate_rating(self, v):
        if not (1 <= v <= 5):
            raise serializers.ValidationError("Note entre 1 et 5.")
        return v


class OfferReportSerializer(serializers.ModelSerializer):
    reporter = serializers.HiddenField(default=serializers.CurrentUserDefault())
    class Meta:
        model = OfferReport
        fields = ["id","offer","reporter","reason","details","status","created_at"]
        read_only_fields = ["status","created_at"]


class OfferCommentSerializer(serializers.ModelSerializer):
    author = serializers.HiddenField(default=serializers.CurrentUserDefault())
    class Meta:
        model = OfferComment
        fields = ["id","offer","author","content","is_public","is_edited","created_at","updated_at"]
        read_only_fields = ["is_edited","created_at","updated_at"]

    def validate_content(self, v):
        if not v or not v.strip():
            raise serializers.ValidationError("Le commentaire ne peut pas être vide.")
        return v
