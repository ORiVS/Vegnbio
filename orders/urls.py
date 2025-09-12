from django.urls import path
from .views import (
    DeliverySlotsView, CartView, CheckoutView,
    MyOrdersView, OrderStatusView
)

urlpatterns = [
    # Créneaux
    path("slots/", DeliverySlotsView.as_view(), name="orders-slots"),

    # Panier
    path("cart/", CartView.as_view(), name="orders-cart"),           # GET = voir / POST = ajouter / DELETE = retirer
    path("checkout/", CheckoutView.as_view(), name="orders-checkout"),

    # Commandes
    path("", MyOrdersView.as_view(), name="orders-myorders"),
    path("<int:pk>/status/", OrderStatusView.as_view(), name="orders-status"),
]
