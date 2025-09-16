from django.conf import settings
from django.db import models
from django.utils import timezone

class Species(models.Model):
    code = models.CharField(max_length=16, unique=True)  # ex: "dog", "cat"
    name = models.CharField(max_length=64)               # ex: "Chien", "Chat"

    def __str__(self):
        return self.name

class Breed(models.Model):
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name="breeds")
    name = models.CharField(max_length=96)

    class Meta:
        unique_together = ("species", "name")

    def __str__(self):
        return f"{self.name} ({self.species.code})"

class Symptom(models.Model):
    code = models.CharField(max_length=64, unique=True)  # ex: "vomiting"
    label = models.CharField(max_length=128)             # ex: "Vomissements"

    def __str__(self):
        return self.label

class Disease(models.Model):
    SEVERITY = (("low","Low"), ("medium","Medium"), ("high","High"))

    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=8, choices=SEVERITY, default="medium")

    # Maladie valable pour quelles espèces ?
    species = models.ManyToManyField(Species, related_name="diseases", blank=True)

    def __str__(self):
        return self.name

class DiseaseSymptom(models.Model):
    KIND = (("MUST", "Must Have"), ("NICE", "Nice To Have"))
    disease = models.ForeignKey(Disease, on_delete=models.CASCADE, related_name="disease_symptoms")
    symptom = models.ForeignKey(Symptom, on_delete=models.CASCADE)
    kind = models.CharField(max_length=4, choices=KIND)

    class Meta:
        unique_together = ("disease", "symptom", "kind")

class DiseaseBreedRisk(models.Model):
    """Poids race × maladie : léger bonus/malus [-0.3 ; +0.3] appliqué au score final."""
    disease = models.ForeignKey(Disease, on_delete=models.CASCADE, related_name="breed_risks")
    breed = models.ForeignKey(Breed, on_delete=models.CASCADE, related_name="disease_risks")
    weight = models.FloatField(default=0.0)  # ex: 0.1 = +10%

    class Meta:
        unique_together = ("disease", "breed")

class Consultation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    species = models.ForeignKey(Species, on_delete=models.PROTECT)
    breed = models.ForeignKey(Breed, null=True, blank=True, on_delete=models.SET_NULL)
    input_symptoms = models.JSONField(default=list)  # ex: ["vomiting","lethargy"]
    predictions = models.JSONField(default=list)     # top-3 renvoyés
    created_at = models.DateTimeField(default=timezone.now)

class Feedback(models.Model):
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name="feedbacks")
    is_useful = models.BooleanField()
    notes = models.TextField(blank=True)
    chosen_diagnosis = models.ForeignKey(Disease, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(default=timezone.now)

class ReportEvent(models.Model):
    """Remontée d'erreurs / signalements (fonctionnels & techniques)."""
    EVENT_TYPE = (("functional","Functional"), ("technical","Technical"))
    CATEGORY = (
        ("missing_symptom","Missing Symptom"),
        ("not_useful","Not Useful"),
        ("underestimated_urgency","Underestimated Urgency"),
        ("bug_ui","UI Bug"),
        ("http_error","HTTP Error"),
        ("timeout","Timeout"),
        ("other","Other"),
    )
    created_at = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    source = models.CharField(max_length=16, default="mobile")  # "mobile" | "web"
    event_type = models.CharField(max_length=16, choices=EVENT_TYPE)
    category = models.CharField(max_length=32, choices=CATEGORY)
    message = models.CharField(max_length=512, blank=True)
    context_json = models.JSONField(default=dict, blank=True)
    consultation = models.ForeignKey(Consultation, null=True, blank=True, on_delete=models.SET_NULL)
    endpoint = models.CharField(max_length=256, blank=True)
    http_status = models.IntegerField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
