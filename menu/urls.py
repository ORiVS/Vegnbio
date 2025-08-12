from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AllergenViewSet, ProductViewSet, DishViewSet, DishAvailabilityViewSet, MenuViewSet

router = DefaultRouter()
router.register(r'allergens', AllergenViewSet, basename='allergens')
router.register(r'products', ProductViewSet, basename='products')
router.register(r'dishes', DishViewSet, basename='dishes')
router.register(r'dish-availability', DishAvailabilityViewSet, basename='dish-availability')
router.register(r'menus', MenuViewSet, basename='menus')

urlpatterns = [path('', include(router.urls))]
