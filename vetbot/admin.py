from django.contrib import admin
from .models import (
    Species, Breed, Symptom, Disease, DiseaseSymptom, DiseaseRedFlag,
    Case, Feedback, ErrorLog
)

@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name")
    search_fields = ("code", "name")

@admin.register(Breed)
class BreedAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "species")
    list_filter = ("species",)
    search_fields = ("name",)

@admin.register(Symptom)
class SymptomAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "label")
    search_fields = ("code", "label")

@admin.register(Disease)
class DiseaseAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "species", "code", "prevalence")
    list_filter = ("species",)
    search_fields = ("name", "code")

@admin.register(DiseaseSymptom)
class DiseaseSymptomAdmin(admin.ModelAdmin):
    list_display = ("id", "disease", "symptom", "weight", "critical")
    list_filter = ("disease", "critical")
    search_fields = ("disease__name", "symptom__code")

@admin.register(DiseaseRedFlag)
class DiseaseRedFlagAdmin(admin.ModelAdmin):
    list_display = ("id", "disease", "text")
    list_filter = ("disease",)
    search_fields = ("disease__name", "text")

@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("id", "species", "triage", "created_at")
    list_filter = ("triage", "species")
    search_fields = ("advice",)
    readonly_fields = ("created_at",)

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "case", "useful", "by_vet", "validated_diagnosis", "created_at")
    list_filter = ("useful", "by_vet")
    search_fields = ("validated_diagnosis", "note")

@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "message", "created_at")
    list_filter = ("type",)
    search_fields = ("message",)
    readonly_fields = ("created_at",)
