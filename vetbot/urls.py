# vetbot/urls.py
from django.urls import path
from . import views
from .views import ParseView, TriageView

app_name = "vetbot"

urlpatterns = [
    path("api/v1/vetbot/parse/", views.ParseView.as_view(), name="parse"),
    path("parse/", ParseView.as_view(), name="vetbot-parse"),
    path("triage/", TriageView.as_view(), name="vetbot-triage"),
]
