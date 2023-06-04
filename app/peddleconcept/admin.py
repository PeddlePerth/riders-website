from django.contrib import admin, messages
from django.forms.widgets import TextInput
from django import forms
from django.db import models, transaction
from django.template.loader import render_to_string
import json
from .models import *
from .actions import download_as_csv

from admin_action_buttons.admin import ActionButtonsMixin
from peddleconcept.deputy_api import DeputyAPI

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
    actions = ['activate_selected', 'disable_selected', 'invite_deputy', 
        'promote_riders', 'make_core', 'make_non_core',
    ]
    search_fields = ('display_name', 'first_name', 'last_name', 'email')

    fieldsets = (
        (None, {
            'fields': ('first_name', 'last_name', 'display_name', 'active', 
                'is_core_rider', 'rider_class', 'override_pay_rate', 'email', 'phone'
            ),
        }),
        ('Rider payment details', {
            'fields': ('abn', 'bank_acct', 'bank_bsb'),
        }),
        ('Advanced options', {
            'fields': ('email_verified', 'user', 'last_seen', 'created', 'source_row_state', 
                'source_row_id', 'source',
            ),
        })
    )

    @admin.action(description='Archive selected riders')
    def disable_selected(self, request, queryset):
        num_updated = queryset.update(active=False, is_core_rider=False, rider_class=None)
        messages.success(request, '%d riders disabled' % num_updated)

    @admin.action(description='Un-archive selected riders')
    def activate_selected(self, request, queryset):
        num_updated = queryset.update(active=True)
        messages.success(request, '%d riders enabled' % num_updated)

    @admin.action(description='Make core riders')
    def make_core(self, request, queryset):
        num_updated = queryset.filter(rider_class__isnull=False).update(is_core_rider=True)
        messages.success(request, '%d riders are now core riders' % num_updated)

    @admin.action(description='Make non-core riders')
    def make_non_core(self, request, queryset):
        num_updated = queryset.update(is_core_rider=False)
        messages.success(request, '%d riders are now non-core riders' % num_updated)

    @admin.action(description='Promote riders')
    def promote_riders(self, request, queryset):
        num_updated = 0
        rider_classes = sorted((c[0] for c in Person.RIDER_CLASS_CHOICES))
        for obj in queryset:
            if not obj.rider_class:
                obj.rider_class = rider_classes[0]
                num_updated += 1
            else:
                i = rider_classes.index(obj.rider_class)
                if i < len(rider_classes) - 1:
                    obj.rider_class = rider_classes[i + 1]
                    num_updated += 1
            obj.save()
        messages.success(request, '%d of %d riders made into riders or promoted' % (num_updated, queryset.count()))

    @admin.display(description='Rider Status')
    def rider_status_html(self, obj):
        return render_to_string('admin/person_rider_status.html', { 'obj': obj })

    @admin.action(description='Invite selected to Deputy')
    def invite_deputy(self, request, queryset):
        api = DeputyAPI(request=request)
        for obj in queryset:
            if obj.has_deputy_account:
                messages.error(request, '%s already has a Deputy account' % obj.name)
                continue
            try:
                api.add_employee(obj, send_invite=True)
            except Exception as e:
                messages.error(request, "Error adding %s to Deputy: %s: %s" % (
                    obj.name, type(e).__name__, str(e),
                ))

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return False
        return super().has_delete_permission(request, obj)
        
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