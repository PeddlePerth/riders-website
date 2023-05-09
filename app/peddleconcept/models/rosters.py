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
        'person', 'area', 'time_start', 'time_end', 'meal_break_mins', 'rest_break_mins',
        'open_shift', 'warning', 'warning_override', 'published', 'shift_notes', 'shift_confirmed'
    )

    person = models.ForeignKey('Person', on_delete=models.SET_NULL, null=True, blank=True,
        help_text='Person rostered to this shift - may be blank for Open or Empty shift.')

    # corresponds to Area in Deputy UI where shift is published
    area = models.ForeignKey('Area', on_delete=models.SET_NULL, null=True)

    # these fields are stored in this model - duplicating Deputy data - as well as the implicit values
    # from the collection of related Tour objects. However the Tour data may change at any time from 
    # external sources - we can use this data to determine whether any changes have occurred and if this
    # affects the Roster and if something should be done about it.
    time_start = models.DateTimeField(default=timezone.now)
    time_end = models.DateTimeField(default=timezone.now)
    meal_break_mins = models.PositiveIntegerField(blank=True, default=0)
    rest_break_mins = models.PositiveIntegerField(blank=True, default=0)
    open_shift = models.BooleanField(blank=True, default=False)
    warning = models.TextField(blank=True, help_text='Warning message from Deputy if chosen person is not preferred')
    warning_override = models.TextField(blank=True, help_text='Comment in Deputy if/why warning is ignored')
    published = models.BooleanField(blank=True, default=False, verbose_name='Publish in Deputy')
    shift_notes = models.TextField(blank=True, default=True)
    shift_confirmed = models.BooleanField(blank=True, default=True)
    timesheet_locked = models.DateTimeField(null=True, blank=True,
        help_text='Date/Time when timesheet was created for this shift')

class RosterTour(models.Model):
    """ intermediate entity providing a list of (non-overlapping) tours for each roster """

    RIDER_ROLE_CHOICES = [
        (x, x) for x in ['tour-lead', 'tour-colead', 'rider']
    ]
    roster = models.ForeignKey(Roster, on_delete=models.CASCADE)
    tour = models.ForeignKey('Tour', on_delete=models.CASCADE)
    rider_role = models.CharField(max_length=20, blank=True, choices=RIDER_ROLE_CHOICES)

    # numeric order of tour in the schedule, ie. first tour is 1, then 2, ...
    # can be used for some consistency checking, in case tour is rescheduled?
    tour_order = models.PositiveIntegerField(blank=True, default=0)