from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SupplierOfferViewSet, OfferReviewViewSet, OfferReportViewSet, OfferCommentViewSet

router = DefaultRouter()
router.register(r'offers', SupplierOfferViewSet, basename='offers')
router.register(r'reviews', OfferReviewViewSet, basename='offer-reviews')
router.register(r'reports', OfferReportViewSet, basename='offer-reports')
router.register(r'comments', OfferCommentViewSet, basename='offer-comments')


urlpatterns = [ path('', include(router.urls)) ]
