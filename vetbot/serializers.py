from rest_framework import serializers
from .models import Species, Breed, Symptom, Disease, Consultation, Feedback, ReportEvent

class SymptomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Symptom
        fields = ("id","code","label")

class BreedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Breed
        fields = ("id","name")

class AskInputSerializer(serializers.Serializer):
    species = serializers.CharField()
    breed_id = serializers.IntegerField(required=False)
    symptoms = serializers.ListField(child=serializers.CharField(), allow_empty=False)

class DiseaseShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disease
        fields = ("id","name")

class PredictionSerializer(serializers.Serializer):
    disease = DiseaseShortSerializer()
    score = serializers.FloatField()
    triage = serializers.CharField()

class AskResponseSerializer(serializers.Serializer):
    predictions = PredictionSerializer(many=True)
    advice = serializers.CharField()
    consultation_id = serializers.IntegerField()

class FeedbackSerializer(serializers.Serializer):
    consultation_id = serializers.IntegerField()
    is_useful = serializers.BooleanField()
    notes = serializers.CharField(required=False, allow_blank=True)
    chosen_diagnosis_id = serializers.IntegerField(required=False)

class ReportEventSerializer(serializers.Serializer):
    event_type = serializers.ChoiceField(choices=["functional","technical"])
    category = serializers.ChoiceField(choices=[
        "missing_symptom","not_useful","underestimated_urgency",
        "bug_ui","http_error","timeout","other"
    ])
    message = serializers.CharField(required=False, allow_blank=True)
    consultation_id = serializers.IntegerField(required=False)
    endpoint = serializers.CharField(required=False, allow_blank=True)
    http_status = serializers.IntegerField(required=False)
    request_id = serializers.CharField(required=False, allow_blank=True)
    context = serializers.DictField(required=False)
    source = serializers.CharField(required=False, default="mobile")
