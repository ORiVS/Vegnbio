# purchasing/admin.py
from django.contrib import admin
from .models import SupplierOrder, SupplierOrderItem

class SupplierOrderItemInline(admin.TabularInline):
    model = SupplierOrderItem
    extra = 0
    fields = ("offer", "qty_requested", "qty_confirmed", "unit_price")
    readonly_fields = ("unit_price",)
    autocomplete_fields = ("offer",)

@admin.register(SupplierOrder)
class SupplierOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id", "status", "restaurateur", "supplier",
        "created_at", "confirmed_at", "items_count", "total_requested"
    )
    list_filter = ("status", "created_at")
    search_fields = ("id", "restaurateur__email", "supplier__email", "note")
    date_hierarchy = "created_at"
    inlines = [SupplierOrderItemInline]
    autocomplete_fields = ("restaurateur", "supplier")
    readonly_fields = ("created_at", "confirmed_at")

    def items_count(self, obj):
        return obj.items.count()

    def total_requested(self, obj):
        from decimal import Decimal
        total = Decimal("0.00")
        for it in obj.items.all():
            qty = it.qty_requested or Decimal("0")
            price = it.unit_price or Decimal("0")
            total += qty * price
        return total
    total_requested.short_description = "Total (demandé)"

@admin.register(SupplierOrderItem)
class SupplierOrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "offer", "qty_requested", "qty_confirmed", "unit_price")
    list_filter = ("order__status",)
    search_fields = ("order__id", "offer__product_name")
    autocomplete_fields = ("order", "offer")
