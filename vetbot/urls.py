from django.urls import path
from .views import SymptomsView, BreedsView, AskView, FeedbackView, ReportEventView, ReportingSummaryView

urlpatterns = [
    path("symptoms/", SymptomsView.as_view()),
    path("breeds/", BreedsView.as_view()),
    path("ask/", AskView.as_view()),
    path("feedback/", FeedbackView.as_view()),
    path("report/", ReportEventView.as_view()),
    path("reporting/summary/", ReportingSummaryView.as_view()),
]
