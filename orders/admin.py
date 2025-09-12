# orders/admin.py
from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import csv
from .models import DeliverySlot, Cart, CartItem, Order, OrderItem


# ===========================
# DeliverySlot (Créneaux)
# ===========================

@admin.register(DeliverySlot)
class DeliverySlotAdmin(admin.ModelAdmin):
    list_display = ("start", "end", "day", "time_range", "duration_minutes")
    date_hierarchy = "start"
    ordering = ("start",)
    search_fields = ("start", "end")
    list_per_page = 50
    actions = ("duplicate_next_day", "duplicate_next_week", "delete_past_slots")

    @admin.display(description=_("Jour"))
    def day(self, obj):
        return obj.start.date()

    @admin.display(description=_("Plage horaire"))
    def time_range(self, obj):
        return f"{obj.start:%H:%M} → {obj.end:%H:%M}"

    @admin.display(description=_("Durée (min)"))
    def duration_minutes(self, obj):
        delta = obj.end - obj.start
        return int(delta.total_seconds() // 60)

    @admin.action(description=_("Dupliquer au lendemain"))
    def duplicate_next_day(self, request, queryset):
        count = 0
        for s in queryset:
            DeliverySlot.objects.create(start=s.start + timezone.timedelta(days=1),
                                        end=s.end + timezone.timedelta(days=1))
            count += 1
        self.message_user(request, _(f"{count} créneau(x) dupliqué(s) au lendemain."))

    @admin.action(description=_("Dupliquer à la semaine suivante"))
    def duplicate_next_week(self, request, queryset):
        count = 0
        for s in queryset:
            DeliverySlot.objects.create(start=s.start + timezone.timedelta(days=7),
                                        end=s.end + timezone.timedelta(days=7))
            count += 1
        self.message_user(request, _(f"{count} créneau(x) dupliqué(s) à J+7."))

    @admin.action(description=_("Supprimer les créneaux passés"))
    def delete_past_slots(self, request, queryset):
        past_qs = DeliverySlot.objects.filter(start__lt=timezone.now())
        count = past_qs.count()
        past_qs.delete()
        self.message_user(request, _(f"{count} créneau(x) passé(s) supprimé(s)."))


# ===========================
# Cart + CartItem (Panier)
# ===========================

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ("external_item_id", "name", "unit_price", "quantity", "line_total")
    readonly_fields = ("line_total",)
    show_change_link = False

    @admin.display(description=_("Total ligne"))
    def line_total(self, obj):
        try:
            return f"{(obj.unit_price * obj.quantity):.2f} €"
        except Exception:
            return "-"


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user_email", "items_count", "total_display", "created_at", "updated_at")
    list_select_related = ("user",)
    search_fields = ("user__email",)
    date_hierarchy = "created_at"
    inlines = [CartItemInline]
    raw_id_fields = ("user",)

    @admin.display(description=_("Email"))
    def user_email(self, obj):
        return getattr(obj.user, "email", "-")

    @admin.display(description=_("Articles"))
    def items_count(self, obj):
        return obj.items.count()

    @admin.display(description=_("Total panier"))
    def total_display(self, obj):
        try:
            return f"{obj.total():.2f} €"
        except Exception:
            return "-"


# ===========================
# Order + OrderItem (Commandes)
# ===========================

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ("external_item_id", "name", "unit_price", "quantity", "line_total")
    readonly_fields = ("external_item_id", "name", "unit_price", "quantity", "line_total")

    @admin.display(description=_("Total ligne"))
    def line_total(self, obj):
        return f"{obj.line_total:.2f} €" if obj and obj.line_total is not None else "-"

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user_email", "status", "created_at",
        "subtotal_display", "discount_points_used", "discount_euros_display", "total_paid_display",
        "city", "postal_code", "slot_id_display",
    )
    list_filter = ("status", "created_at")
    list_select_related = ("user", "slot")
    search_fields = ("id", "user__email", "address_line1", "city", "postal_code")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]
    raw_id_fields = ("user", "slot")
    actions = (
        "mark_preparing", "mark_out_for_delivery", "mark_delivered", "mark_cancelled",
        "export_csv",
    )
    readonly_fields = (
        "created_at", "subtotal", "discount_points_used", "discount_euros", "total_paid",
    )

    # ==== Colonnes formatées ====
    @admin.display(description=_("Email"))
    def user_email(self, obj):
        return getattr(obj.user, "email", "-")

    @admin.display(description=_("Sous-total"))
    def subtotal_display(self, obj):
        return f"{obj.subtotal:.2f} €"

    @admin.display(description=_("Remise (€)"))
    def discount_euros_display(self, obj):
        return f"{obj.discount_euros:.2f} €"

    @admin.display(description=_("Total payé"))
    def total_paid_display(self, obj):
        return f"{obj.total_paid:.2f} €"

    @admin.display(description=_("Créneau"))
    def slot_id_display(self, obj):
        return getattr(obj.slot, "id", "-")

    # ==== Actions statut ====
    @admin.action(description=_("Marquer « En préparation »"))
    def mark_preparing(self, request, queryset):
        updated = queryset.update(status=Order.PREPARING)
        self.message_user(request, _(f"{updated} commande(s) mise(s) « En préparation »."))

    @admin.action(description=_("Marquer « En livraison »"))
    def mark_out_for_delivery(self, request, queryset):
        updated = queryset.update(status=Order.OUT_FOR_DELIVERY)
        self.message_user(request, _(f"{updated} commande(s) mise(s) « En livraison »."))

    @admin.action(description=_("Marquer « Livrée »"))
    def mark_delivered(self, request, queryset):
        updated = queryset.update(status=Order.DELIVERED)
        self.message_user(request, _(f"{updated} commande(s) marquée(s) « Livrée »."))

    @admin.action(description=_("Marquer « Annulée »"))
    def mark_cancelled(self, request, queryset):
        updated = queryset.update(status=Order.CANCELLED)
        self.message_user(request, _(f"{updated} commande(s) marquée(s) « Annulée »."))

    # ==== Export CSV ====
    @admin.action(description=_("Exporter en CSV"))
    def export_csv(self, request, queryset):
        fieldnames = [
            "id", "user_email", "created_at", "status",
            "subtotal", "discount_points_used", "discount_euros", "total_paid",
            "address_line1", "address_line2", "city", "postal_code", "phone",
            "slot_id",
        ]
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="orders.csv"'
        writer = csv.DictWriter(response, fieldnames=fieldnames)
        writer.writeheader()
        for o in queryset.select_related("user", "slot"):
            writer.writerow({
                "id": o.id,
                "user_email": getattr(o.user, "email", ""),
                "created_at": o.created_at.isoformat(),
                "status": o.status,
                "subtotal": f"{o.subtotal:.2f}",
                "discount_points_used": o.discount_points_used,
                "discount_euros": f"{o.discount_euros:.2f}",
                "total_paid": f"{o.total_paid:.2f}",
                "address_line1": o.address_line1,
                "address_line2": o.address_line2,
                "city": o.city,
                "postal_code": o.postal_code,
                "phone": o.phone,
                "slot_id": getattr(o.slot, "id", ""),
            })
        return response


# ===========================
# (Optionnel) Admin dédiés items
# ===========================

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "name", "quantity", "unit_price")
    list_select_related = ("cart",)
    search_fields = ("name", "external_item_id", "cart__user__email")
    raw_id_fields = ("cart",)

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "name", "quantity", "unit_price", "line_total")
    list_select_related = ("order",)
    search_fields = ("name", "external_item_id", "order__user__email")
    raw_id_fields = ("order",)
