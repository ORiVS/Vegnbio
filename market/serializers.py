from rest_framework import serializers
from .models import SupplierOffer, OfferReview, OfferReport, REGION_IDF, REGIONS_ALLOWED
from menu.models import Allergen, Product  # import Product pour l'import direct

class SupplierOfferSerializer(serializers.ModelSerializer):
    supplier = serializers.HiddenField(default=serializers.CurrentUserDefault())
    allergens = serializers.PrimaryKeyRelatedField(queryset=Allergen.objects.all(), many=True, required=False)
    avg_rating = serializers.SerializerMethodField()

    class Meta:
        model = SupplierOffer
        fields = ["id","supplier","product_name","description","is_bio","producer_name","region","allergens",
                  "unit","price","min_order_qty","stock_qty","available_from","available_to","status",
                  "avg_rating","created_at"]
        read_only_fields = ["status","avg_rating","created_at"]

    def get_avg_rating(self, obj):
        qs = obj.reviews.all().values_list("rating", flat=True)
        return round(sum(qs)/len(qs), 2) if qs else None

    def validate(self, data):
        if self.context["request"].user.role != "FOURNISSEUR":
            raise serializers.ValidationError("Seuls les fournisseurs peuvent créer/éditer des offres.")
        if "region" in data and data["region"] not in REGIONS_ALLOWED:
            raise serializers.ValidationError("Région non autorisée. Exigence: Île-de-France.")
        if data.get("price", 0) < 0 or data.get("min_order_qty", 0) <= 0:
            raise serializers.ValidationError("Prix et quantité minimale doivent être positifs.")
        rating = self.initial_data.get("rating")
        if rating is not None and (int(rating) < 1 or int(rating) > 5):
            raise serializers.ValidationError("La note doit être entre 1 et 5.")
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
