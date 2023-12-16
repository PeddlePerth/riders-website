from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import date, datetime, time
import json
import logging

from peddleconcept.util import json_datetime

logger = logging.getLogger(__name__)

class Settings(models.Model):
    class Meta:
        verbose_name = 'Settings (Advanced)'
        verbose_name_plural = 'Settings (Advanced)'
    name = models.CharField(max_length=100, unique=True)
    data = models.JSONField(default=dict)

    def __str__(self):
        return self.name

class ScheduledTask(models.Model):
    class Meta:
        verbose_name = 'Scheduled task (Advanced)'
        verbose_name_plural = 'Scheduled tasks (Advanced)'

    TASK_STATE_CHOICES = [
        (x, x) for x in ['disabled', 'pending', 'running', 'error', 'timeout']
    ]
    name = models.CharField(max_length=100)
    task_state = models.CharField(max_length=20, default='pending', choices=TASK_STATE_CHOICES)
    last_run_time = models.DateTimeField(default=timezone.now)
    last_finish_time = models.DateTimeField(default=timezone.now)
    last_run_message = models.TextField(blank=True)
    last_run_log = models.TextField(blank=True)
    run_interval_minutes = models.PositiveIntegerField(blank=True, default=30)
    run_timeout_minutes = models.PositiveIntegerField(blank=True, default=2)

class ChangeLog(models.Model):
    """ Represents addition/change/deletion or similar with regard to some model and some external data system """

    CHANGE_REMOTE_CHOICES = [
        (x, x) for x in ['rezdy', 'fringe', 'deputy', 'local-history']
    ]
    
    CHANGE_TYPE_CHOICES = [
        (x, x) for x in ['deleted', 'undeleted', 'created', 'changed']
    ]

    model_type = models.CharField(max_length=30, blank=True)
    model_description = models.TextField(blank=True)

    change_remote = models.CharField(max_length=20, null=True, blank=True, choices=CHANGE_REMOTE_CHOICES)
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPE_CHOICES)
    change_description = models.TextField(blank=True)
    data = models.JSONField(blank=True, null=True)

    timestamp = models.DateTimeField(default=timezone.now)
    timestamp_saved = models.DateTimeField(auto_now_add=True)

class MutableDataRecord(models.Model):
    """
    Generic base class for a record which has an immutable unique ID and tracks changes to itself, with certain mutable fields.
    Changes can come from different sources, and can apply to mutable fields. Immutable fields such as ID would be ignored if they appear in changes.
    This could be implemented very _neatly_ with metaclasses but that's a lot of technical work and could introduce heaps of potential weird bugs
    BUT ALSO METACLASSES ARE FREAKIN AWESOME
    """
    CHANGE_SOURCES = {
        'rezdy': {'auto': True},
        'fringe': {'auto': True},
        'deputy': {'auto': True},
        '': {'auto': True},
        'auto': {'auto': True},
        'generate_sessions': {'auto': True},
        'generate_pay_report': {'auto': True},
        'user': {'auto': False},
    }

    CHANGE_SOURCES_CHOICES = [ (x, x) for x in CHANGE_SOURCES.keys() ]
    SOURCE_ROW_STATE_CHOICES = [ 
        (x, x) for x in [
            'live', # source row was last seen to exist with ID=source_row_id
            'deleted', # source row was not found in last check - assume it was deleted remotely
            'none', # source row may or may not exist with ID=source_row_id: match (as opposed to creating new row) but don't propagate changes
            'pending', # local row created, pending creation of source row
        ]
    ]

    # Mutable fields are ones which can be modified by the user AND auto-updated, eg. whatever the thing should keep tabs on
    MUTABLE_FIELDS = ()
    IMMUTABLE_FIELDS = ('source_row_id', 'source_row_state', 'id', 'source', 'field_auto_values', 'updated', 'created')

    # some non-fungible identity for the source row, eg. Rezdy order_id
    source_row_id = models.CharField(max_length=300, null=True, blank=True,
        help_text="External ID for this item (eg. Rezdy/Fringe booking number)")
    source_row_state = models.CharField(max_length=50, null=True, blank=True, choices=SOURCE_ROW_STATE_CHOICES,
        help_text="State of the external data row") # 'live' or 'deleted'

    # brief machine-friendly description of data source, eg. "rezdy", "fringe", "user"
    source = models.CharField(max_length=50, blank=True, choices=CHANGE_SOURCES_CHOICES,
        help_text="External data source")

    # keep track of the latest "auto" value of each field
    # compare with the actual field value, to determine if the field is in the "auto" state (and can be automatically updated)
    # or if there is a change (ie. actual != auto value) then it has been modified by the user and should NOT be auto-updated
    field_auto_values = models.JSONField(default=dict, blank=True,
        help_text="External/automatic values for each of the fields")

    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)
    class Meta:
        abstract = True # this is an abstract model, must be subclassed for specific data

    def __init__(self, *args, **kwargs):
        """ Hook to call update_field() on initial data passed to the Model constructor """
        source = kwargs.get('source', '')

        # copy mutable field values from kwargs
        data = {}
        for key in kwargs.keys():
            if key in self.MUTABLE_FIELDS:
                data[key] = kwargs[key]
        super().__init__(*args, **kwargs)

        for field, value in data.items():
            self.update_field(field, value, source)

    def update_field(self, field_name, new_value, source=None):
        """
        Try to update the field with a new value, where the source
        and the field's auto-update state determines if it goes through or not
        """
        timestamp = int(timezone.now().timestamp())
        is_auto_update = self.CHANGE_SOURCES.get(source, {}).get('auto', True)

        if not isinstance(self.field_auto_values, dict):
            self.field_auto_values = {}
        
        has_auto_value = field_name in self.field_auto_values
        auto_value = self.field_auto_values.get(field_name)
        actual_value = getattr(self, field_name)

        can_auto_update = auto_value == actual_value or not has_auto_value
        if has_auto_value and isinstance(actual_value, (date, datetime)):
            can_auto_update = auto_value == json_datetime(actual_value)

        changed = False
        if can_auto_update or not is_auto_update:
            # make the data change here
            if getattr(self, field_name) != new_value:
                setattr(self, field_name, new_value)
                changed = True
        
        if is_auto_update and field_name in self.MUTABLE_FIELDS:
            # update the 'auto' value corresponding to the data source
            if isinstance(new_value, (date, datetime)):
                new_value = json_datetime(new_value)
            self.field_auto_values[field_name] = new_value

        return changed

    def update_from_dict(self, data, source=None):
        num_updates = 0
        for field, value in data.items():
            if not field in self.MUTABLE_FIELDS:
                continue
            if self.update_field(field, value, source):
                num_updates += 1
        return num_updates

    def update_from_instance(self, src_row):
        """
        Copies changes from another MutableDataRow model instance, 
        returns ChangeLog instance if any changes.
        """
        if not isinstance(src_row, MutableDataRecord):
            logger.error('Bad model merge between %s and %s: source=%s' % (
                type(src_row), getattr(src_row, 'source', None), type(self)))
            return None

        self.source = src_row.source
        
        chg_fields = {}
        for field in self.MUTABLE_FIELDS:
            orig_value = getattr(self, field)
            if self.update_field(field, getattr(src_row, field)):
                new_value = getattr(self, field)
                if isinstance(orig_value, (date, datetime, time)):
                    chg_fields[field] = (orig_value.isoformat(), new_value.isoformat())
                else:
                    chg_fields[field] = (orig_value, new_value)

        if self.source_row_state != 'live':
            logger.warning('update_from_instance: Model %s id %s has source_row_state=%s expected LIVE' % (
                type(self).__name__, self.pk, self.source_row_state
            ))
            chg_fields['source_row_state'] = (self.source_row_state, 'live')
            self.source_row_state = 'live'
        
        if chg_fields:
            return ChangeLog(
                model_type = self._meta.model_name,
                change_remote = self.source,
                change_type = 'changed',
                model_description = '%s [pk=%s source_row_id=%s]' % (
                    str(self), self.pk, self.source_row_id,
                ),
                change_description = 'changed: %s' % (
                    '\n'.join('%s --> %s' % (f, v) for f, v in chg_fields.items())
                ),
            )

    def mark_update_pushed(self, src_row):
        """ Marks row as updated in remote DB """
        if (chglog := src_row.update_from_instance(self)):
            chglog.change_type = 'push_change'
            return chglog

    def mark_source_deleted(self, push=False):
        """ Marks row as deleted from data source """
        if self.source_row_state == 'deleted':
            return # nothing to do
        self.source_row_state = 'deleted'
        return ChangeLog(
            model_type = self._meta.model_name,
            change_remote = self.source,
            change_type = 'deleted' if not push else 'push_delete',
            model_description = '%s [pk=%s source_row_id=%s]' % (
                str(self), self.pk, self.source_row_id, 
            ),
            change_description = 'source_row_id=%s pk=%s not found: %s' % (self.source_row_id, self.pk, str(self)),
        )

    def mark_source_added(self, push=False):
        """ Returns changelog for row when first found in data source """
        if self.source_row_state == 'live' and self.pk:
            return # nothing to do
        
        if self.source_row_state == 'deleted':
            # row has been undeleted somehow: possible from glitches in the source data
            return ChangeLog(
                model_type = self._meta.model_name,
                change_remote = self.source,
                change_type = 'undeleted' if not push else 'push_recreate',
                model_description = '%s [pk=%s source_row_id=%s]' % (
                    str(self), self.pk, self.source_row_id,
                ),
                change_description = 'source_row_id=%s pk=%s undeleted: %s' % (self.source_row_id, self.pk, str(self)),
            )
        else:
            return ChangeLog(
                model_type = self._meta.model_name,
                change_remote = self.source,
                change_type = 'created' if not push else 'push_create',
                model_description = '%s [pk=%s source_row_id=%s]' % (
                    str(self), self.pk, self.source_row_id,
                ),
                change_description = 'source_row_id=%s pk=%s created: %s' % (self.source_row_id, self.pk, str(self)),
            )
        self.source_row_state = 'live'

