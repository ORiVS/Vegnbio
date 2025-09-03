# restaurants/admin.py
from django.contrib import admin
from django.utils import timezone

from .models import (
    Restaurant, Room, Reservation,
    Evenement, EvenementRegistration, EventInvite,
    RestaurantClosure,
)

# ---------- INLINES ----------

class RoomInline(admin.TabularInline):
    model = Room
    extra = 1
    fields = ("name", "capacity")
    show_change_link = True

class EvenementInline(admin.TabularInline):
    """Voir/éditer rapidement les évènements depuis la fiche Restaurant."""
    model = Evenement
    extra = 0
    fields = ("title", "type", "date", "start_time", "end_time",
              "status", "is_public", "is_blocking", "room", "capacity")
    show_change_link = True

class RestaurantClosureInline(admin.TabularInline):
    """Fermetures exceptionnelles affichées sur la fiche Restaurant."""
    model = RestaurantClosure
    extra = 0
    fields = ("date", "reason")
    show_change_link = True


class EventInviteInline(admin.TabularInline):
    """Invitations visibles/éditables sur la fiche Évènement."""
    model = EventInvite
    extra = 0
    fields = ("email", "phone", "status", "token", "created_at", "expires_at")
    readonly_fields = ("token", "created_at", "expires_at")
    show_change_link = True

class EvenementRegistrationInline(admin.TabularInline):
    """Inscriptions visibles sur la fiche Évènement (en lecture seule)."""
    model = EvenementRegistration
    extra = 0
    fields = ("user", "created_at")
    readonly_fields = ("user", "created_at")
    can_delete = False
    show_change_link = True


# ---------- RESTAURANT ----------

@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = (
        "name", "city", "postal_code", "capacity",
        "wifi_available", "printer_available", "owner",
    )
    search_fields = ("name", "city", "owner__email")
    list_filter = (
        "city", "wifi_available", "printer_available",
        "member_trays_available", "delivery_trays_available",
        "animations_enabled",
    )
    fieldsets = (
        ("Informations générales", {
            "fields": ("name", "address", "city", "postal_code", "capacity", "owner")
        }),
        ("Services disponibles", {
            "fields": (
                "wifi_available", "printer_available",
                "member_trays_available", "delivery_trays_available",
                "animations_enabled", "animation_day",
            )
        }),
        ("Horaires d’ouverture", {
            "fields": (
                ("opening_time_mon_to_thu", "closing_time_mon_to_thu"),
                ("opening_time_friday", "closing_time_friday"),
                ("opening_time_saturday", "closing_time_saturday"),
                ("opening_time_sunday", "closing_time_sunday"),
            )
        }),
    )
    inlines = [RoomInline, EvenementInline, RestaurantClosureInline]

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "capacity")
    search_fields = ("name", "restaurant__name", "restaurant__city")
    list_filter = ("restaurant",)
    autocomplete_fields = ("restaurant",)

# ---------- RESERVATION ----------

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "id", "customer", "restaurant_for_list", "room", "full_restaurant",
        "date", "start_time", "end_time", "status", "created_at",
    )
    list_filter = ("status", "date", "full_restaurant")
    search_fields = ("customer__email", "customer__first_name", "customer__last_name",
                     "room__name", "room__restaurant__name", "restaurant__name")
    readonly_fields = ("created_at",)
    date_hierarchy = "date"
    list_select_related = ("room", "restaurant", "customer")

    @admin.display(description="Restaurant")
    def restaurant_for_list(self, obj):
        # Affiche toujours le nom du resto (que la résa soit room ou full_restaurant)
        if obj.restaurant:
            return obj.restaurant.name
        if obj.room and obj.room.restaurant:
            return obj.room.restaurant.name
        return "—"


# ---------- EVENEMENT ----------

@admin.register(Evenement)
class EvenementAdmin(admin.ModelAdmin):
    list_display = (
        "id", "title", "restaurant", "room", "type",
        "date", "start_time", "end_time",
        "status", "is_public", "is_blocking", "capacity",
        "published_at", "full_at", "cancelled_at",
    )
    list_filter = (
        "restaurant", "type", "status", "is_public", "is_blocking", "date", "room",
    )
    search_fields = ("title", "description", "restaurant__name", "room__name")
    date_hierarchy = "date"
    autocomplete_fields = ("restaurant", "room")
    inlines = [EventInviteInline, EvenementRegistrationInline]
    list_select_related = ("restaurant", "room")
    readonly_fields = (
        # Ces champs existent si tu as bien fait les migrations suggérées
        "created_at", "updated_at", "published_at", "full_at", "cancelled_at",
    )

    # ----- Actions rapides -----
    actions = ("action_publish", "action_cancel", "action_close", "action_reopen")

    @admin.action(description="Publier les évènements sélectionnés")
    def action_publish(self, request, queryset):
        count = 0
        now = timezone.now()
        for ev in queryset:
            if ev.status in ("DRAFT", "CANCELLED"):
                ev.status = "PUBLISHED"
                # si le champ existe, on le remplit
                if hasattr(ev, "published_at"):
                    ev.published_at = now
                ev.save()
                count += 1
        self.message_user(request, f"{count} évènement(s) publié(s).")

    @admin.action(description="Annuler les évènements sélectionnés")
    def action_cancel(self, request, queryset):
        count = 0
        now = timezone.now()
        for ev in queryset:
            ev.status = "CANCELLED"
            if hasattr(ev, "cancelled_at"):
                ev.cancelled_at = now
            ev.save()
            count += 1
        self.message_user(request, f"{count} évènement(s) annulé(s).")

    @admin.action(description="Marquer COMPLET les évènements sélectionnés")
    def action_close(self, request, queryset):
        count = 0
        now = timezone.now()
        for ev in queryset:
            ev.status = "FULL"
            if hasattr(ev, "full_at"):
                ev.full_at = now
            ev.save()
            count += 1
        self.message_user(request, f"{count} évènement(s) marqué(s) complet(s).")

    @admin.action(description="Réouvrir les évènements sélectionnés")
    def action_reopen(self, request, queryset):
        count = 0
        for ev in queryset:
            ev.status = "PUBLISHED"
            ev.save()
            count += 1
        self.message_user(request, f"{count} évènement(s) réouvert(s).")


# ---------- INVITATIONS ----------

@admin.register(EventInvite)
class EventInviteAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "email", "phone", "status", "created_at", "expires_at", "token")
    list_filter = ("status", "event__restaurant")
    search_fields = ("email", "phone", "token", "event__title", "event__restaurant__name")
    autocomplete_fields = ("event",)
    readonly_fields = ("token", "created_at", "expires_at")
    date_hierarchy = "created_at"

    actions = ("mark_pending", "mark_accepted", "mark_revoked")

    @admin.action(description="Marquer PENDING")
    def mark_pending(self, request, queryset):
        updated = queryset.update(status="PENDING")
        self.message_user(request, f"{updated} invitation(s) marquée(s) PENDING.")

    @admin.action(description="Marquer ACCEPTED")
    def mark_accepted(self, request, queryset):
        updated = queryset.update(status="ACCEPTED")
        self.message_user(request, f"{updated} invitation(s) marquée(s) ACCEPTED.")

    @admin.action(description="Marquer REVOKED")
    def mark_revoked(self, request, queryset):
        updated = queryset.update(status="REVOKED")
        self.message_user(request, f"{updated} invitation(s) marquée(s) REVOKED.")


# ---------- INSCRIPTIONS ----------

@admin.register(EvenementRegistration)
class EvenementRegistrationAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "user", "created_at")
    list_filter = ("event__restaurant",)
    search_fields = ("event__title", "user__email", "user__first_name", "user__last_name")
    autocomplete_fields = ("event", "user")
    date_hierarchy = "created_at"
    list_select_related = ("event", "user")


# ---------- FERMETURES ----------

@admin.register(RestaurantClosure)
class RestaurantClosureAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "date", "reason", "created_at")
    list_filter = ("restaurant", "date")
    search_fields = ("restaurant__name", "reason")
    autocomplete_fields = ("restaurant",)
    date_hierarchy = "date"
