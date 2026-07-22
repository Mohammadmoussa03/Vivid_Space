from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ('-date_joined',)
    list_display = ('email', 'first_name', 'last_name', 'role', 'email_verified',
                    'is_approved', 'is_active')
    list_filter = ('role', 'email_verified', 'is_approved', 'is_active', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name', 'company')
    readonly_fields = ('date_joined', 'last_login')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Profile', {'fields': ('first_name', 'last_name', 'company')}),
        ('Access', {'fields': ('role', 'email_verified', 'is_approved', 'is_active',
                               'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role',
                       'is_approved', 'password1', 'password2'),
        }),
    )

    actions = ['approve_users']

    @admin.action(description='Approve selected users')
    def approve_users(self, request, queryset):
        queryset.update(is_approved=True)
