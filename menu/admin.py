from django.contrib import admin
from .models import Allergen, Product, Dish, DishAvailability, Menu, MenuItem

@admin.register(Allergen)
class AllergenAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "label")
    search_fields = ("code", "label")

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_bio", "producer_name", "region")
    search_fields = ("name", "producer_name", "region")
    filter_horizontal = ("allergens",)

@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_vegan")
    search_fields = ("name",)
    filter_horizontal = ("products",)

@admin.register(DishAvailability)
class DishAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("id", "dish", "restaurant", "date", "is_available")
    list_filter = ("restaurant", "date", "is_available")
    search_fields = ("dish__name", "restaurant__name")

class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 0
    autocomplete_fields = ("dish",)

@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "start_date", "end_date")
    search_fields = ("title",)
    inlines = [MenuItemInline]
