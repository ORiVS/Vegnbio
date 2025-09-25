from rest_framework import serializers

class ParseInputSerializer(serializers.Serializer):
    text = serializers.CharField()

class ParseOutputSerializer(serializers.Serializer):
    species = serializers.CharField()
    breed = serializers.CharField(allow_blank=True)
    symptoms = serializers.ListField(child=serializers.DictField())

class TriageInputSerializer(serializers.Serializer):
    species = serializers.CharField()
    breed = serializers.CharField(required=False, allow_blank=True)
    symptoms = serializers.ListField(child=serializers.CharField())

class TriageOutputSerializer(serializers.Serializer):
    triage = serializers.ChoiceField(choices=["low", "medium", "high"])
    differential = serializers.ListField(child=serializers.DictField())
    red_flags = serializers.ListField(child=serializers.CharField())
    advice = serializers.CharField()
