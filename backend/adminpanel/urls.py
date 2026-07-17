from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminBlockedSlotViewSet,
    AdminClientViewSet,
    AdminCustomizationViewSet,
    AdminDashboardView,
    AdminFAQViewSet,
    AdminGalleryViewSet,
    AdminOrderViewSet,
    AdminPackageCategoryViewSet,
    AdminPackageViewSet,
    AdminPromoCodeViewSet,
    AdminReservationViewSet,
    AdminSettingsView,
    AdminSpaceViewSet,
    AdminTourViewSet,
    AdminUserViewSet,
    GalleryUploadView,
    SiteContentView,
)

router = DefaultRouter()
router.register('users', AdminUserViewSet, basename='admin-user')
router.register('clients', AdminClientViewSet, basename='admin-client')
router.register('reservations', AdminReservationViewSet, basename='admin-reservation')
router.register('orders', AdminOrderViewSet, basename='admin-order')
router.register('spaces', AdminSpaceViewSet, basename='admin-space')
router.register('packages', AdminPackageViewSet, basename='admin-package')
router.register('categories', AdminPackageCategoryViewSet, basename='admin-category')
router.register('gallery', AdminGalleryViewSet, basename='admin-gallery')
router.register('faqs', AdminFAQViewSet, basename='admin-faq')
router.register('promo-codes', AdminPromoCodeViewSet, basename='admin-promo-code')
router.register('tours', AdminTourViewSet, basename='admin-tour')
router.register('customizations', AdminCustomizationViewSet, basename='admin-customization')
router.register('blocked-slots', AdminBlockedSlotViewSet, basename='admin-blocked-slot')

urlpatterns = [
    path('dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('content/', SiteContentView.as_view(), name='admin-content'),
    path('settings/', AdminSettingsView.as_view(), name='admin-settings'),
    path('upload/', GalleryUploadView.as_view(), name='admin-upload'),
    path('', include(router.urls)),
]
