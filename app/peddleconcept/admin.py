from django.contrib import admin, messages
from django.forms.widgets import TextInput
from django import forms
from django.db import models, transaction
from django.template.loader import render_to_string
import json
from .models import *
from .actions import download_as_csv

from admin_action_buttons.admin import ActionButtonsMixin

class MyJSONFormField(forms.JSONField):
    def prepare_value(self, value):
        if isinstance(value, forms.fields.InvalidJSONInput):
            return value
        return json.dumps(value, ensure_ascii=False, indent=4, cls=self.encoder)

class MyModelAdmin(ActionButtonsMixin, admin.ModelAdmin):
    def get_form(self, request, obj=None, **kwargs):
        field_classes = {
            field.name: MyJSONFormField
            for field in self.model._meta.fields if isinstance(field, models.JSONField)
        }
        return super().get_form(request, obj, field_classes=field_classes, **kwargs)

#@admin.register(Rider)
#class RiderAdmin(MyModelAdmin):
#    list_display = ('name', 'display_name', 'phone', 'email', 'user')

class TourRiderInline(admin.TabularInline):
    model = TourRider
    fields = ['person', 'rider_role']
    formfield_overrides = {
        models.TextField: {'widget': TextInput},
        models.JSONField: {'widget': TextInput},
    }

class TourVenueInline(admin.TabularInline):
    model = TourVenue
    fields = ['venue', 'activity', 'time_arrive', 'time_depart', 'notes']
    formfield_overrides = {
        models.TextField: {'widget': TextInput},
        models.JSONField: {'widget': TextInput},
    }

@admin.register(TourRider)
class TourRiderAdmin(MyModelAdmin):
    list_display = ('__str__', 'tour', 'person')
    list_filter = ('tour__time_start', 'tour__tour_type')
    ordering = ['-tour__time_start']

@admin.register(TourVenue)
class TourVenueAdmin(MyModelAdmin):
    list_display = ('__str__', 'tour', 'venue')
    list_filter = ('tour__time_start', 'tour__tour_type', 'venue')
    ordering = ['-tour__time_start']

@admin.register(Session)
class SessionAdmin(MyModelAdmin):
    list_display = ('source_row_id', 'session_type', 'source', 'time_start', 'time_end', 'updated')
    list_filter = ('source', 'source_row_state', 'time_start', 'session_type')
    ordering = ['-time_start', 'session_type']
    search_fields = ('source_row_id', 'session_type', )

@admin.register(Venue)
class VenueAdmin(MyModelAdmin):
    list_display = ('name', 'drink_special')


@admin.register(Tour)
class TourAdmin(MyModelAdmin):
    list_display = ('source_row_id', 'customer_name', 'tour_area', 'tour_type', 'time_start', 'time_end', 'updated')
    list_filter = ('source', 'source_row_state', 'time_start', 'tour_area', 'tour_type')
    ordering = ['-time_start', 'tour_type']
    search_fields = ['source_row_id', 'customer_name']
    inlines = (TourRiderInline, TourVenueInline)
    formfield_overrides = {
        models.TextField: {'widget': TextInput}
    }

@admin.register(RiderPaySlot)
class RiderPaySlotAdmin(MyModelAdmin):
    list_display = ('__str__', 'person', 'time_start', 'time_end', 'pay_minutes')
    list_filter = ('person', 'time_start')

@admin.register(Settings)
class SettingsAdmin(MyModelAdmin):
    list_display = ('name', 'data')

@admin.register(ChangeLog)
class ChangeLogAdmin(MyModelAdmin):
    list_display = ('model_type', 'change_remote', 'change_type', 'model_description', 'timestamp')
    list_filter = ('model_type', 'change_remote', 'change_type', 'timestamp')
    ordering = ['-timestamp']
    search_fields = ('model_description', 'change_description')

    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(Person)
class PersonAdmin(MyModelAdmin):
    list_display = (
        '__str__', 'rider_status_html',
        'override_pay_rate', 'email', 'phone', 'last_seen',)
    list_filter = ('active', 'source_row_state', 'email_verified', 'rider_class', 'is_core_rider', 'override_pay_rate')
    ordering = ['-active', '-rider_class']
    actions = ['disable_selected', 'delete_selected']
    search_fields = ('display_name', 'first_name', 'last_name', 'email')

    @admin.action(description='Disable selected accounts')
    def disable_selected(self, request, queryset):
        num_updated = queryset.update(active=False)
        messages.success('%d riders disabled' % num_updated)

    @admin.display(description='Rider Status')
    def rider_status_html(self, obj):
        return render_to_string('admin/person_rider_status.html', { 'obj': obj })


@admin.register(PersonToken)
class PersonTokenAdmin(MyModelAdmin):
    list_display = (
        'person', 'action', 'valid_from', 'full_url'
    )
    ordering = ['action', 'person__first_name']
    list_filter = ('valid_days', 'action', 'person__active')
    exclude = ['token']
    readonly_fields = ['person']

@admin.register(Area)
class AreaAdmin(MyModelAdmin):
    list_display = (
        'name', 'tour_locations_html', 'active', 'deputy_sync_enabled'
    )
    ordering = ['sort_order']
    list_filter = ['active', 'deputy_sync_enabled']
    search_fields = ['tour_locations']
    actions = ['disable_sync', 'enable_sync']

    @admin.display(description='Tour Pickup Locations')
    def tour_locations_html(self, obj):
        return render_to_string('admin/area_tour_locations.html', {'obj': obj})

    @transaction.atomic
    @admin.action(description='Disable Deputy sync')
    def disable_sync(self, request, queryset):
        """ mark objects as 'offline' whether or not there is a corresponding Deputy row """
        num_update = 0
        for obj in queryset:
            if obj.source_row_state != 'none':
                obj.source_row_state = 'none'
                obj.save()
                num_update += 1

        messages.success(request, "Sync disabled for %d items" % num_update)