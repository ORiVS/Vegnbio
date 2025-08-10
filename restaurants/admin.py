from django.contrib import admin
from .models import Restaurant, Room, Reservation

class RoomInline(admin.TabularInline):
    model = Room
    extra = 1  # permet d’ajouter 1 salle directement depuis la fiche restaurant


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'postal_code', 'capacity', 'wifi_available', 'printer_available', 'owner')
    search_fields = ('name', 'city', 'owner__email')
    list_filter = ('city', 'wifi_available', 'printer_available', 'member_trays_available', 'delivery_trays_available')
    fieldsets = (
        ("Informations générales", {
            'fields': ('name', 'address', 'city', 'postal_code', 'capacity', 'owner')
        }),
        ("Services disponibles", {
            'fields': (
                'wifi_available',
                'printer_available',
                'member_trays_available',
                'delivery_trays_available',
                'animations_enabled',
                'animation_day'
            )
        }),
        ("Horaires d’ouverture", {
            'fields': (
                ('opening_time_mon_to_thu', 'closing_time_mon_to_thu'),
                ('opening_time_friday', 'closing_time_friday'),
                ('opening_time_saturday', 'closing_time_saturday'),
                ('opening_time_sunday', 'closing_time_sunday'),
            )
        }),
    )
    inlines = [RoomInline]


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('customer', 'room', 'date', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'date')
    search_fields = ('customer__email', 'room__name')
    readonly_fields = ('created_at',)
