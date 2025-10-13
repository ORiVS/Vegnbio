from rest_framework import serializers


# parse
class ParseInputSerializer(serializers.Serializer):
    text = serializers.CharField()


class ParseOutputSerializer(serializers.Serializer):
    species = serializers.CharField()
    breed = serializers.CharField(allow_blank=True)
    symptoms = serializers.ListField(child=serializers.DictField())


# triage
class TriageInputSerializer(serializers.Serializer):
    species = serializers.CharField()
    breed = serializers.CharField(required=False, allow_blank=True)
    symptoms = serializers.ListField(child=serializers.CharField())


class TriageOutputSerializer(serializers.Serializer):
    triage = serializers.ChoiceField(choices=["low", "medium", "high"])
    differential = serializers.ListField(child=serializers.DictField())
    red_flags = serializers.ListField(child=serializers.CharField())
    advice = serializers.CharField()


# listes utilitaires
class SpeciesSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()


class BreedSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class SymptomSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()


class DiseaseDebugSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    code = serializers.CharField(allow_null=True)
    prevalence = serializers.FloatField()


# feedback
class FeedbackInputSerializer(serializers.Serializer):
    case_id = serializers.IntegerField()
    useful = serializers.BooleanField(required=False, allow_null=True)
    validated_diagnosis = serializers.CharField(required=False, allow_blank=True)
    by_vet = serializers.BooleanField(required=False, default=False)
    note = serializers.CharField(required=False, allow_blank=True)


class FeedbackOutputSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField()


# stats
class StatsOutputSerializer(serializers.Serializer):
    total_cases = serializers.IntegerField()
    cases_per_day = serializers.ListField(child=serializers.DictField())  # [{"day":"2025-10-14","count":X}, ...]
    top_symptoms = serializers.ListField(child=serializers.DictField())   # [{"code":"vomiting","count":10}, ...]
    top_diseases = serializers.ListField(child=serializers.DictField())   # [{"name":"Gastro...","count":7}, ...]
    feedback_useful_rate = serializers.FloatField()
