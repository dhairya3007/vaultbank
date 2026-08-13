from django.contrib import admin
from .models import Locker, Customer, LockerUser, AccessLog


class LockerUserInline(admin.TabularInline):
    model = LockerUser
    extra = 1
    max_num = 3


@admin.register(Locker)
class LockerAdmin(admin.ModelAdmin):
    list_display = ('locker_number', 'token', 'is_active', 'get_customer_count')
    list_filter = ('is_active',)
    search_fields = ('locker_number', 'token')
    readonly_fields = ('token',)
    inlines = [LockerUserInline]

    def get_customer_count(self, obj):
        return obj.customer_count
    get_customer_count.short_description = 'Customers'


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'id_proof_type')
    search_fields = ('name',)
    list_filter = ('id_proof_type',)


@admin.register(LockerUser)
class LockerUserAdmin(admin.ModelAdmin):
    list_display = ('customer', 'locker', 'assigned_at')
    list_filter = ('locker',)
    search_fields = ('customer__name', 'locker__locker_number')


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ('customer', 'locker', 'check_in_time', 'check_out_time', 'is_active')
    list_filter = ('locker', 'check_out_time')
    search_fields = ('customer__name', 'locker__locker_number')
    readonly_fields = ('check_in_time',)
