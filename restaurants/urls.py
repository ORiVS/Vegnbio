from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RestaurantViewSet, RoomViewSet, ReservationViewSet, restaurant_reservations_view, \
    availability_dashboard, all_reservations_view, reservations_stats_view, EvenementViewSet

router = DefaultRouter()
router.register(r'restaurants', RestaurantViewSet, basename='restaurants')
router.register(r'rooms', RoomViewSet, basename='rooms')
router.register(r'reservations', ReservationViewSet, basename='reservations')
router.register(r'evenements', EvenementViewSet, basename='evenements')


urlpatterns = [
    path('', include(router.urls)),
    path('restaurants/<int:restaurant_id>/reservations/', restaurant_reservations_view, name='restaurant-reservations'),
    path('restaurants/<int:restaurant_id>/dashboard/', availability_dashboard, name='availability-dashboard'),
    path('reservations/all/', all_reservations_view, name='all-reservations'),
    path('reservations/statistics/', reservations_stats_view, name='reservation-statistics'),
]
