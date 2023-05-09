from django.contrib import admin
from django.forms.widgets import TextInput
from django import forms
from django.db import models
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


@admin.register(Venue)
class VenueAdmin(MyModelAdmin):
    list_display = ('name', 'drink_special')


@admin.register(Tour)
class TourAdmin(MyModelAdmin):
    list_display = ('source_row_id', 'customer_name', 'tour_type', 'time_start', 'time_end', 'updated')
    list_filter = ('source', 'source_row_state', 'time_start', 'tour_type')
    ordering = ['-time_start', 'tour_type']
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

    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(Person)
class PersonAdmin(MyModelAdmin):
    list_display = (
        'name', 'email', 'email_verified',
        'rider_class', 'is_core_rider', 'override_pay_rate', 'active', 'last_seen', 'created')
    list_filter = ('active', 'source_row_state', 'email_verified', 'rider_class', 'is_core_rider', 'override_pay_rate')

@admin.register(PersonToken)
class PersonTokenAdmin(MyModelAdmin):
    list_display = (
        'person', 'action', 'valid_from', 'full_url'
    )
    ordering = ['action', 'person__first_name']
    list_filter = ('valid_days', 'action', 'person__active')
    exclude = ['token']
    readonly_fields = ['person']