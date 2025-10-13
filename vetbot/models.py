from django.conf import settings
from django.db import models
from django.utils import timezone


class Species(models.Model):
    code = models.CharField(max_length=32, unique=True)      # ex: "dog", "cat"
    name = models.CharField(max_length=64)                   # ex: "Chien", "Chat"

    class Meta:
        verbose_name_plural = "Species"
        indexes = [models.Index(fields=["code"])]

    def __str__(self):
        return self.name


class Breed(models.Model):
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name="breeds")
    name = models.CharField(max_length=96)
    aliases = models.JSONField(default=list, blank=True)     # ex: ["Labrador Retriever", "Lab"]

    class Meta:
        unique_together = ("species", "name")
        indexes = [models.Index(fields=["species", "name"])]

    def __str__(self):
        return f"{self.name} ({self.species.code})"


class Symptom(models.Model):
    code = models.CharField(max_length=64, unique=True)      # ex: "vomiting", "fever"
    label = models.CharField(max_length=128)                 # ex: "Vomissements", "Fièvre"
    snomed_id = models.CharField(max_length=32, blank=True)  # optionnel
    venom_code = models.CharField(max_length=32, blank=True) # optionnel

    class Meta:
        indexes = [models.Index(fields=["code"])]

    def __str__(self):
        return self.label


class Disease(models.Model):
    code = models.CharField(max_length=64, blank=True, null=True)  # peut être null au début
    name = models.CharField(max_length=128)
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name="diseases")
    description = models.TextField(blank=True)
    references = models.JSONField(default=list, blank=True)
    prevalence = models.FloatField(default=0.0)  # petit bonus dans le scoring

    class Meta:
        indexes = [
            models.Index(fields=["species", "code"]),
            models.Index(fields=["species", "name"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.species.code})"


class DiseaseSymptom(models.Model):
    disease = models.ForeignKey(Disease, on_delete=models.CASCADE, related_name="symptom_links")
    symptom = models.ForeignKey(Symptom, on_delete=models.CASCADE, related_name="disease_links")
    weight = models.FloatField(default=1.0)     # importance du symptôme pour cette maladie
    critical = models.BooleanField(default=False)

    class Meta:
        unique_together = ("disease", "symptom")
        indexes = [models.Index(fields=["disease", "symptom"])]

    def __str__(self):
        return f"{self.disease.name} ↔ {self.symptom.label} (w={self.weight}, critical={self.critical})"


class DiseaseRedFlag(models.Model):
    disease = models.ForeignKey(Disease, on_delete=models.CASCADE, related_name="red_flags")
    text = models.CharField(max_length=256)

    def __str__(self):
        return f"⚠ {self.disease.name}: {self.text}"


class Case(models.Model):
    TRIAGE_LOW = "low"
    TRIAGE_MEDIUM = "medium"
    TRIAGE_HIGH = "high"
    TRIAGE_CHOICES = [
        (TRIAGE_LOW, "Low"),
        (TRIAGE_MEDIUM, "Medium"),
        (TRIAGE_HIGH, "High"),
    ]

    species = models.ForeignKey(Species, on_delete=models.SET_NULL, null=True, related_name="cases")
    breed = models.ForeignKey(Breed, on_delete=models.SET_NULL, null=True, blank=True, related_name="cases")
    user_text = models.TextField(blank=True)  # texte saisi par l’utilisateur

    extracted_symptoms = models.JSONField(default=list, blank=True)  # symptômes extraits bruts (avec durée, sévérité…)
    symptom_codes = models.JSONField(default=list, blank=True)       # codes finaux (["vomiting","fever"])

    triage = models.CharField(max_length=10, choices=TRIAGE_CHOICES, blank=True)
    differential = models.JSONField(default=list, blank=True)  # top-N: [{disease, prob, why}]
    advice = models.TextField(blank=True)                     # conseils prudents

    model_trace = models.JSONField(default=dict, blank=True)  # prompts/params/ids pour audit
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Case #{self.id} {self.species and self.species.code} triage={self.triage or '-'}"


class Feedback(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="feedbacks", null=True, blank=True)
    useful = models.BooleanField(null=True, blank=True)
    validated_diagnosis = models.CharField(max_length=128, blank=True)  # si confirmé plus tard
    by_vet = models.BooleanField(default=False)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Feedback case={self.case_id} useful={self.useful}"


class ErrorLog(models.Model):
    TYPE_LLM_ERROR = "LLM_ERROR"
    TYPE_NON_JSON = "NON_JSON_RESPONSE"
    TYPE_UNKNOWN_SYMPTOM = "UNKNOWN_SYMPTOM"
    TYPE_TIMEOUT = "TIMEOUT"

    type = models.CharField(max_length=32)
    message = models.CharField(max_length=256, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.type} - {self.message or ''}"
