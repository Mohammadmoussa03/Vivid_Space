from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AvailabilityView,
    BookingViewSet,
    CategoryListView,
    CustomizationRequestView,
    FAQListView,
    GalleryListView,
    OverviewView,
    PackageViewSet,
    ScheduleChangeView,
    SiteConfigView,
    SpaceViewSet,
    TourRequestCreateView,
)

router = DefaultRouter()
router.register('spaces', SpaceViewSet, basename='space')
router.register('bookings', BookingViewSet, basename='booking')
router.register('packages', PackageViewSet, basename='package')
router.register('categories', CategoryListView, basename='category')
router.register('gallery', GalleryListView, basename='gallery')
router.register('faqs', FAQListView, basename='faq')
router.register('tours', TourRequestCreateView, basename='tour')

urlpatterns = [
    path('overview/', OverviewView.as_view(), name='overview'),
    path('schedule-change/', ScheduleChangeView.as_view(), name='schedule-change'),
    path('customize/', CustomizationRequestView.as_view(), name='customize'),
    path('availability/', AvailabilityView.as_view(), name='availability'),
    path('site/', SiteConfigView.as_view(), name='site-config'),
    path('', include(router.urls)),
]
