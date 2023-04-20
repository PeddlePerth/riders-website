from django.db import models
from django.conf import settings
from django.utils import timezone
from peddleconcept.util import json_datetime

from .base import MutableDataRecord

class Timesheet(models.Model):
    """ Timesheet model for payroll - takes copy of data from each Roster """
    roster = models.ForeignKey('Roster', on_delete=models.SET_NULL, null=True, 
        help_text='Associated rostered shift object, if any')
    person = models.ForeignKey('Person', on_delete=models.CASCADE)

    time_start = models.DateTimeField(default=timezone.now)
    time_end = models.DateTimeField(default=timezone.now)
    meal_break_mins = models.PositiveIntegerField(blank=True, default=0)
    rest_break_mins = models.PositiveIntegerField(blank=True, default=0)
    shift_notes = models.TextField(blank=True)
    
    pay_rate = models.IntegerField(blank=True, default=0)
    pay_hours = models.FloatField(blank=True, default=0)

    timesheet_notes = models.TextField(blank=True)
    approved = models.BooleanField(blank=True, default=True) # this may not be needed?
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    approved_time = models.DateTimeField(default=timezone.now)

class RiderPaySlot(MutableDataRecord):
    class Meta:
        verbose_name = 'Rider Pay Slot (Advanced)'
        verbose_name_plural = 'Rider Pay Slots (Advanced)'
    
    MUTABLE_FIELDS = ('slot_type', 'pay_rate', 'pay_reason', 'pay_minutes', 'description')
    # rider removed
    #rider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    person = models.ForeignKey('Person', on_delete=models.CASCADE, null=True)
    
    slot_type = models.CharField(
        max_length=10, null=False, blank=False,
        choices=[(x, x) for x in ('tour', 'break', 'manual')], default='manual')
    tour_rider = models.ForeignKey('TourRider', on_delete=models.SET_NULL, null=True)
    pay_rate = models.PositiveIntegerField(default=30)
    pay_reason = models.CharField(max_length=200, blank=True)
    description = models.CharField(max_length=1000, blank=True)
    pay_minutes = models.PositiveIntegerField(default=0)
    time_start = models.DateTimeField()
    time_end = models.DateTimeField()

    def to_json(self):
        return {
            'id': self.id,
            'rider_id': self.person.id,
            'slot_type': self.slot_type,
            'tour_rider_id': self.tour_rider.id if self.tour_rider else None,
            'pay_rate': self.pay_rate,
            'pay_reason': self.pay_reason,
            'pay_minutes': self.pay_minutes,
            'description': self.description,
            'time_start': json_datetime(self.time_start),
            'time_end': json_datetime(self.time_end),
            'field_auto_values': self.field_auto_values,
        }
