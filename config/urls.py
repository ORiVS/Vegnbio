from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),
    path('api/restaurants/', include('restaurants.urls')),
    path('api/menu/', include('menu.urls')),
    path('api/market/', include(('market.urls', 'market'), namespace='market')),
    path('api/pos/', include('pos.urls')),
    path("api/fidelite/", include("fidelite.urls")),
    path("api/orders/", include("orders.urls")),
]
