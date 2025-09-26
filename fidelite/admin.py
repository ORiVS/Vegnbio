# fidelite/admin.py
from django.contrib import admin
from .models import LoyaltyProgram, Membership, PointsTransaction

@admin.register(LoyaltyProgram)
class LoyaltyProgramAdmin(admin.ModelAdmin):
    list_display = ("name", "earn_rate_per_euro", "redeem_rate_euro_per_point", "created_at")
    readonly_fields = ("created_at",)

    def has_add_permission(self, request):
        # on force le "singleton" : un seul enregistrement de config
        if LoyaltyProgram.objects.exists():
            return False
        return super().has_add_permission(request)

class PointsTransactionInline(admin.TabularInline):
    model = PointsTransaction
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("kind", "points", "reason", "related_order_id", "created_at")
    can_delete = False

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "points_balance", "joined_at")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    readonly_fields = ("joined_at",)
    inlines = [PointsTransactionInline]

@admin.register(PointsTransaction)
class PointsTransactionAdmin(admin.ModelAdmin):
    list_display = ("membership", "kind", "points", "reason", "related_order_id", "created_at")
    list_filter = ("kind", "created_at")
    search_fields = ("reason", "related_order_id", "membership__user__email")
    readonly_fields = ("created_at",)
