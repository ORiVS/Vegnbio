from rest_framework import serializers

from restaurants.models import Restaurant
from .models import Allergen, Product, Dish, DishAvailability, Menu, MenuItem

# --- Allergènes ---
class AllergenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergen
        fields = ["id", "code", "label"]


# --- Produits ---
class ProductSerializer(serializers.ModelSerializer):
    allergens = serializers.PrimaryKeyRelatedField(queryset=Allergen.objects.all(), many=True, required=False)

    class Meta:
        model = Product
        fields = ["id", "name", "is_bio", "producer_name", "region", "is_vegetarian", "allergens"]


# --- Plats ---
class DishSerializer(serializers.ModelSerializer):
    products = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), many=True, required=False)
    extra_allergens = serializers.PrimaryKeyRelatedField(queryset=Allergen.objects.all(), many=True, required=False)
    allergens = serializers.SerializerMethodField()

    class Meta:
        model = Dish
        fields = ["id", "name", "description", "price", "is_vegan", "is_active",
                  "products", "extra_allergens", "allergens"]

    def get_allergens(self, obj):
        return list(obj.allergens_union_qs().values("id", "code", "label"))

    def validate(self, data):
        # Bloquer un plat avec un product non végétarien
        prods = data.get("products", []) or getattr(self.instance, "products", None)
        if prods:
            if any([not p.is_vegetarian for p in prods]):
                raise serializers.ValidationError("Tous les produits doivent être végétariens.")
        return data


# --- Disponibilités ---
class DishAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = DishAvailability
        fields = ["id", "dish", "restaurant", "date", "is_available"]


# --- Menu & Items ---
class MenuItemSerializer(serializers.ModelSerializer):
    # on renvoie le plat complet (lecture)
    dish = DishSerializer(read_only=True)
    # et on accepte un id en écriture pour ne pas casser create/update
    dish_id = serializers.PrimaryKeyRelatedField(
        queryset=Dish.objects.all(),
        source="dish",
        write_only=True
    )

    class Meta:
        model = MenuItem
        fields = ["id", "dish", "dish_id", "course_type"]


class MenuSerializer(serializers.ModelSerializer):
    items = MenuItemSerializer(many=True)
    restaurants = serializers.PrimaryKeyRelatedField(queryset=Restaurant.objects.all(), many=True)

    class Meta:
        model = Menu
        fields = ["id", "title", "description", "start_date", "end_date", "restaurants", "is_published", "items"]

    def validate(self, data):
        if data["end_date"] < data["start_date"]:
            raise serializers.ValidationError("end_date doit être ≥ start_date")
        return data

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        restaurants = validated_data.pop("restaurants", [])
        menu = Menu.objects.create(**validated_data)
        menu.restaurants.set(restaurants)
        for item in items_data:
            MenuItem.objects.create(menu=menu, **item)
        return menu

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        restaurants = validated_data.pop("restaurants", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if restaurants is not None:
            instance.restaurants.set(restaurants)
        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                MenuItem.objects.create(menu=instance, **item)
        return instance
