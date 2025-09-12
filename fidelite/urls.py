from django.urls import path
from .views import JoinProgramView, PointsBalanceView, TransactionsListView, SpendPointsView

urlpatterns = [
    path("join/", JoinProgramView.as_view(), name="fidelite-join"),
    path("points/", PointsBalanceView.as_view(), name="fidelite-points"),
    path("transactions/", TransactionsListView.as_view(), name="fidelite-transactions"),
    path("use/", SpendPointsView.as_view(), name="fidelite-use"),
]
