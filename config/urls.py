# config/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Veg'N Bio API",
        default_version="v1",
        description="Documentation de l'API",
        contact=openapi.Contact(email="orivsdogbevi@gmail.com"),
        license=openapi.License(name="MIT"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/accounts/', include('accounts.urls')),
    path('api/restaurants/', include('restaurants.urls')),
    path('api/menu/', include('menu.urls')),

    path('api/market/', include(('market.urls', 'market'), namespace='market')),
    path('api/purchasing/', include(('purchasing.urls', 'purchasing'), namespace='purchasing')),

    path('api/pos/', include('pos.urls')),
    path("api/fidelite/", include("fidelite.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/vetbot/", include("vetbot.urls")),

    re_path(r"^swagger(?P<format>\.json|\.yaml)$",
            schema_view.without_ui(cache_timeout=0), name="schema-json"),
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0),
         name="schema-swagger-ui"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0),
         name="schema-redoc"),

]
