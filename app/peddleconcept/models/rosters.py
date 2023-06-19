from django.db import models
from django.conf import settings
from django.utils import timezone
from peddleconcept.util import json_datetime

from .base import MutableDataRecord

class Roster(MutableDataRecord):
    """
    A shift on the roster, ie. a time period where a particular person is expected to work.
    Corresponds 1:1 with Deputy Roster.
    """
    MUTABLE_FIELDS = (
        'person', 'area', 'time_start', 'time_end', 'open_shift', 'approval_required',
        'warning_comment', 'warning_override_comment', 'published', 'shift_notes', 
        #'confirm_status', 'swap_status',
    )

    person = models.ForeignKey('Person', on_delete=models.SET_NULL, null=True, blank=True,
        help_text='Person rostered to this shift - may be blank for Open shift.')

    # corresponds to Area in Deputy UI where shift is published
    area = models.ForeignKey('Area', on_delete=models.SET_NULL, null=True)

    # these fields are stored in this model - duplicating Deputy data - as well as the implicit values
    # from the collection of related Tour objects. However the Tour data may change at any time from 
    # external sources - we can use this data to determine whether any changes have occurred and if this
    # affects the Roster and if something should be done about it.
    time_start = models.DateTimeField(default=timezone.now)
    time_end = models.DateTimeField(default=timezone.now)
    open_shift = models.BooleanField(blank=True, default=False)
    approval_required = models.BooleanField(blank=True, default=False)
    warning_comment = models.TextField(blank=True)
    warning_override_comment = models.TextField(blank=True)
    published = models.BooleanField(blank=True, default=False, verbose_name='Publish in Deputy')
    shift_notes = models.TextField(blank=True)
    confirm_status = models.PositiveIntegerField(null=True, blank=True)
    swap_status = models.PositiveIntegerField(null=True, blank=True)

    tour_slots = models.JSONField(default=list)

    def cmp_key(self):
        """ return a hashable string value representing the roster for easy comparison with other rosters """
        return "%s_%d_%d_%s" % (
            self.person.source_row_id if self.person else '',
            self.time_start.timestamp(),
            self.time_end.timestamp(),
            ",".join((
                "%d_%d" % (slot['time_start'] // 1000, slot['time_end'] // 1000)
                for slot in self.tour_slots if slot['type'] == 'break'
            )) if isinstance(self.tour_slots, list) else '',
        )

    def to_json(self):
        return {
            'cmp_key': self.cmp_key(),
            'rider_name': self.person.name if self.person else None,
            'time_start': json_datetime(self.time_start),
            'time_end': json_datetime(self.time_end),
            'open_shift': self.open_shift,
            'approval_required': self.approval_required,
            'warning_comment': self.warning_comment,
            'warning_override_comment': self.warning_override_comment,
            'published': self.published,
            'shift_notes': self.shift_notes,
            'source_row_state': self.source_row_state,
            'source_row_id': self.source_row_id,
            'readonly': getattr(self, '_is_manual', False),
        }
        