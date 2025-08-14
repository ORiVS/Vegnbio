from django.contrib import admin
from .models import CustomUser, UserProfile

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ("email", "first_name", "last_name", "role", "is_active", "is_staff", "date_joined")
    list_filter  = ("role", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name")  # <- requis pour autocomplete_fields ailleurs
    ordering = ("-date_joined",)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "address")
    search_fields = ("user__email", "user__first_name", "user__last_name", "phone")
