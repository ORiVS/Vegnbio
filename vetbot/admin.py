from django.contrib import admin
from .models import (
    Species, Breed, Symptom,
    Disease, DiseaseSymptom, DiseaseRedFlag,
    Case, Feedback
)

@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(Breed)
class BreedAdmin(admin.ModelAdmin):
    list_display = ("name", "species")
    list_filter = ("species",)
    search_fields = ("name",)


@admin.register(Symptom)
class SymptomAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "snomed_id", "venom_code")
    search_fields = ("code", "label", "snomed_id", "venom_code")


class DiseaseSymptomInline(admin.TabularInline):
    model = DiseaseSymptom
    extra = 1


class DiseaseRedFlagInline(admin.TabularInline):
    model = DiseaseRedFlag
    extra = 1


@admin.register(Disease)
class DiseaseAdmin(admin.ModelAdmin):
    list_display = ("name", "species", "code", "prevalence")
    list_filter = ("species",)
    search_fields = ("name", "code")
    inlines = [DiseaseSymptomInline, DiseaseRedFlagInline]


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("id", "species", "breed", "triage", "created_at")
    list_filter = ("triage", "species")
    search_fields = ("user_text",)
    readonly_fields = ("created_at",)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("case", "useful", "by_vet", "created_at")
    list_filter = ("useful", "by_vet")
    search_fields = ("validated_diagnosis", "note")
    readonly_fields = ("created_at",)
