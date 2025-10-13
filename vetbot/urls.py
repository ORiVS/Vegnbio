from django.urls import path
from .views import (
    ParseView, TriageView,
    SpeciesListView, BreedListView, SymptomListView, DiseaseBySpeciesView,
    FeedbackView, StatsView
)

app_name = "vetbot"

urlpatterns = [
    # extraction/triage
    path("api/v1/vetbot/parse/", ParseView.as_view(), name="parse"),
    path("api/v1/vetbot/triage/", TriageView.as_view(), name="triage"),

    # listes utilitaires
    path("api/v1/vetbot/species/", SpeciesListView.as_view(), name="species"),
    path("api/v1/vetbot/breeds/", BreedListView.as_view(), name="breeds"),  # ?species=dog
    path("api/v1/vetbot/symptoms/", SymptomListView.as_view(), name="symptoms"),
    path("api/v1/vetbot/diseases/", DiseaseBySpeciesView.as_view(), name="diseases"),  # ?species=dog (debug)

    # feedback + stats
    path("api/v1/vetbot/feedback/", FeedbackView.as_view(), name="feedback"),
    path("api/v1/vetbot/stats/", StatsView.as_view(), name="stats"),
]
