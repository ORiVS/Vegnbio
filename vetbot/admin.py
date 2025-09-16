from django.contrib import admin
from .models import Species, Breed, Symptom, Disease, DiseaseSymptom, DiseaseBreedRisk, Consultation, Feedback, ReportEvent

admin.site.register(Species)
admin.site.register(Breed)
admin.site.register(Symptom)
admin.site.register(Disease)
admin.site.register(DiseaseSymptom)
admin.site.register(DiseaseBreedRisk)
admin.site.register(Consultation)
admin.site.register(Feedback)
admin.site.register(ReportEvent)
