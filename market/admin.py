from django.contrib import admin
from .models import SupplierOffer, OfferReview, OfferReport, OfferComment


# ---------- Inlines ----------

class OfferReviewInline(admin.TabularInline):
    model = OfferReview
    extra = 0
    fields = ("author", "rating", "comment", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("author",)

class OfferReportInline(admin.TabularInline):
    model = OfferReport
    extra = 0
    fields = ("reporter", "reason", "status", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("reporter",)

# ---------- Actions ----------

@admin.action(description="Publish selected offers")
def publish_offers(modeladmin, request, queryset):
    queryset.update(status="PUBLISHED")

@admin.action(description="Unlist selected offers")
def unlist_offers(modeladmin, request, queryset):
    queryset.update(status="UNLISTED")

@admin.action(description="Move selected offers to Draft")
def draft_offers(modeladmin, request, queryset):
    queryset.update(status="DRAFT")

@admin.action(description="Flag selected offers")
def flag_offers(modeladmin, request, queryset):
    queryset.update(status="FLAGGED")

# ---------- ModelAdmins ----------

@admin.register(SupplierOffer)
class SupplierOfferAdmin(admin.ModelAdmin):
    list_display = (
        "id", "product_name", "supplier", "price", "unit",
        "stock_qty", "is_bio", "region", "status", "available_from", "available_to",
        "created_at",
    )
    list_filter = (
        "status", "is_bio", "region",
        ("available_from", admin.DateFieldListFilter),
        ("available_to", admin.DateFieldListFilter),
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "product_name", "producer_name", "description",
        "supplier__email", "supplier__first_name", "supplier__last_name",
    )
    readonly_fields = ("created_at",)
    autocomplete_fields = ("supplier", "allergens")
    filter_horizontal = ("allergens",)  # pratique si tu n'utilises pas autocomplete
    date_hierarchy = "created_at"
    inlines = [OfferReviewInline, OfferReportInline]
    actions = [publish_offers, unlist_offers, draft_offers, flag_offers]
    list_per_page = 50
    ordering = ("-created_at",)

@admin.register(OfferReview)
class OfferReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "offer", "author", "rating", "created_at")
    list_filter = (("created_at", admin.DateFieldListFilter), "rating")
    search_fields = (
        "offer__product_name",
        "author__email", "author__first_name", "author__last_name",
        "comment",
    )
    autocomplete_fields = ("offer", "author")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

@admin.register(OfferReport)
class OfferReportAdmin(admin.ModelAdmin):
    list_display = ("id", "offer", "reporter", "reason", "status", "created_at")
    list_filter = ("status", ("created_at", admin.DateFieldListFilter))
    search_fields = (
        "offer__product_name",
        "reporter__email", "reporter__first_name", "reporter__last_name",
        "reason", "details",
    )
    autocomplete_fields = ("offer", "reporter")
    readonly_fields = ("created_at",)
    actions = ["mark_reviewed", "mark_action_taken"]
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    @admin.action(description="Mark as REVIEWED")
    def mark_reviewed(self, request, queryset):
        queryset.update(status="REVIEWED")

    @admin.action(description="Mark as ACTION_TAKEN")
    def mark_action_taken(self, request, queryset):
        queryset.update(status="ACTION_TAKEN")

@admin.register(OfferComment)
class OfferCommentAdmin(admin.ModelAdmin):
    list_display = ("id","offer","author","is_public","is_edited","created_at")
    list_filter = ("is_public", ("created_at", admin.DateFieldListFilter))
    search_fields = ("content","offer__product_name","author__email")
    autocomplete_fields = ("offer","author")
