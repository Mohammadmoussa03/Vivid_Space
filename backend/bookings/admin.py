from django.contrib import admin

from .models import (
    AdminSettings, BlockedSlot, Booking, FAQ, GalleryImage, Membership,
    MembershipPlan, PackageCategory, PromoCode, SiteContent, Space, TourRequest,
)


@admin.register(PackageCategory)
class PackageCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order', 'is_visible')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'display_price', 'room_hours', 'is_active',
                    'is_visible', 'is_archived', 'order')
    list_filter = ('category', 'is_active', 'is_visible', 'is_archived', 'featured')


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'effective_hours', 'room_hours_used', 'hours_period')
    list_filter = ('status',)


@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'is_free', 'uses_free_hours', 'units', 'is_active', 'order')
    list_filter = ('is_free', 'uses_free_hours', 'is_active')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('user', 'space', 'unit', 'date', 'duration', 'status', 'is_free', 'is_paid')
    list_filter = ('status', 'duration', 'is_free', 'is_paid')
    date_hierarchy = 'date'


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'campaign', 'sales_rep', 'is_active', 'tour_count')
    list_filter = ('is_active',)


@admin.register(TourRequest)
class TourRequestAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'phone', 'promo_code', 'status', 'created_at')
    list_filter = ('status',)
    date_hierarchy = 'created_at'


@admin.register(BlockedSlot)
class BlockedSlotAdmin(admin.ModelAdmin):
    list_display = ('space', 'date', 'start_time', 'end_time', 'reason')
    date_hierarchy = 'date'


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ('caption', 'category', 'order', 'is_visible')
    list_filter = ('category', 'is_visible')


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'order', 'is_visible')
    list_filter = ('is_visible',)


admin.site.register(SiteContent)
admin.site.register(AdminSettings)
