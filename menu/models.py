from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from restaurants.models import Restaurant

# --- Référentiel d’allergènes ---
class Allergen(models.Model):
    code = models.CharField(max_length=32, unique=True)  # ex: GLUTEN, SOJA, LAIT, ARAchides...
    label = models.CharField(max_length=100)

    class Meta:
        ordering = ["label"]

    def __str__(self):
        return f"{self.label} ({self.code})"


# --- Produits/ingrédients (traçabilité bio + origine locale) ---
class Product(models.Model):
    name = models.CharField(max_length=120)
    is_bio = models.BooleanField(default=True)  # bio par défaut (exigence Veg'N Bio)
    producer_name = models.CharField(max_length=120, blank=True, null=True)
    region = models.CharField(max_length=120, default="Île-de-France")  # local par défaut
    is_vegetarian = models.BooleanField(default=True)  # sécurité anti-écart

    allergens = models.ManyToManyField(Allergen, blank=True, related_name="products")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# --- Plats (union des allergènes des produits, tous végétariens) ---
class Dish(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_vegan = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # M2M vers produits et allergènes additionnels (override si besoin)
    products = models.ManyToManyField(Product, related_name="dishes", blank=True)
    extra_allergens = models.ManyToManyField(Allergen, blank=True, related_name="dishes_extra")

    # cache d’affichage (optionnel) si tu veux éviter de recalculer tout le temps
    # computed_allergens = models.ManyToManyField(Allergen, blank=True, related_name="dishes_computed")

    class Meta:
        ordering = ["name"]

    def clean(self):
        # Interdire un plat non végétarien (exigence)
        if self.products.filter(is_vegetarian=False).exists():
            raise ValidationError("Un plat ne peut pas contenir de produit non végétarien.")

    def __str__(self):
        return self.name

    def allergens_union_qs(self):
        # Union: allergènes des produits + extra_allergens
        ids = set(self.products.values_list("allergens__id", flat=True)) - {None}
        ids |= set(self.extra_allergens.values_list("id", flat=True))
        return Allergen.objects.filter(id__in=ids)


# --- Disponibilité locale d’un plat (rupture / restau spécifique / date) ---
class DishAvailability(models.Model):
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name="availabilities")
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="dish_availabilities")
    date = models.DateField()  # par jour
    is_available = models.BooleanField(default=True)

    class Meta:
        unique_together = ("dish", "restaurant", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.dish} @ {self.restaurant} {self.date}: {'OK' if self.is_available else 'RUPTURE'}"


# --- Menu + items (publication + multi-restaurants + validité) ---
class Menu(models.Model):
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    restaurants = models.ManyToManyField(Restaurant, related_name="menus")
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date", "title"]

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError("La date de fin doit être ≥ date de début.")
        if not self.items.exists():
            # On tolère la création vide, mais empêcher la publication vide
            pass

    def __str__(self):
        return self.title


class MenuItem(models.Model):
    COURSE_CHOICES = [("ENTREE", "Entrée"), ("PLAT", "Plat"), ("DESSERT", "Dessert"), ("BOISSON", "Boisson")]
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="items")
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name="menu_items")
    course_type = models.CharField(max_length=16, choices=COURSE_CHOICES)

    class Meta:
        unique_together = ("menu", "dish", "course_type")
        ordering = ["menu", "course_type"]

    def __str__(self):
        return f"{self.menu} - {self.course_type} - {self.dish}"
