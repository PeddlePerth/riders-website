from django.db import models
from django.conf import settings
from django.utils import timezone
from peddleconcept.util import json_datetime, abbreviate, format_time
from datetime import date

from .base import MutableDataRecord

class Area(MutableDataRecord):
    """
    Model corresponding to OperationalUnit (Area) in Deputy API.
    See https://developer.deputy.com/deputy-docs/docs/operational-unit-1
    Used to configure the Tour Areas sections
    """
    MUTABLE_FIELDS = (
        'area_name', 'colour', 'sort_order'
    )
    area_name = models.CharField(max_length=200, blank=True, verbose_name='Area name in Deputy')
    display_name = models.CharField(max_length=200, blank=True, verbose_name='Area display name')
    colour = models.CharField(max_length=50, null=True, blank=True, verbose_name='Hex colour code')
    tour_locations = models.JSONField(default=dict, blank=True,
        help_text='JSON list of strings being each tour pickup location included under this area')
    sort_order = models.IntegerField(blank=True, default=0)
    active = models.BooleanField(blank=True, default=True, verbose_name='Show to riders')
    deputy_sync_enabled = models.BooleanField(blank=True, default=False, 
        help_text='If enabled, the Area data and associated shifts are pushed to Deputy and can overwrite other changes')
    
    @property
    def locations_list(self):
        data_json = self.tour_locations if isinstance(self.tour_locations, dict) else {}
        data_list = data_json.get('pickup_locations_exact')
        return [str(item).lower().strip() for item in data_list] if isinstance(data_list, list) else []
    
    @property
    def locations_keywords(self):
        data_json = self.tour_locations if isinstance(self.tour_locations, dict) else {}
        data_list = data_json.get('pickup_locations_keyword')
        return [str(item).lower().strip() for item in data_list] if isinstance(data_list, list) else []

    @property
    def name(self):
        return self.display_name or self.area_name

    def __str__(self):
        return 'Tour area: %s' % self.name

class Venue(models.Model):
    name = models.CharField(max_length=200, help_text="Name of venue to show on schedules & in the editor")
    drink_special = models.CharField(max_length=100, blank=True, help_text="Specials/Notes to auto-fill in the schedule")
    contact_email = models.EmailField(blank=True, help_text="Contact Email to display on Venue Bookings summary")
    contact_phone = models.CharField(max_length=20, blank=True, help_text='Contact phone number (if known)')
    contact_name = models.CharField(max_length=100, blank=True, help_text='Contact Name for bar to display on Venue Bookings summary')
    venue_area = models.ForeignKey(Area, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return "%s [%s]" % (self.name, (self.drink_special or 'NO SPECIAL'))

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_short': abbreviate(self.name),
            'notes': self.drink_special,
            'contact_email': self.contact_email,
            'contact_phone': self.contact_phone,
            'contact_name': self.contact_name,
        }

class Session(MutableDataRecord):
    """
    Scheduled tour session / event / performance.
    Tours are grouped by session in the Tour Schedule.
    """
    class Meta:
        verbose_name = 'Tour Session'

    MUTABLE_FIELDS = ('session_type', 'time_start', 'time_end', 'session_note', 'title')

    # sessions in Fringe have a unique ID on import so we have to fudge one by mixing data
    # Rezdy sessions DO have a unique ID - surprise!
    session_type = models.CharField(max_length=200, blank=True)
    time_start = models.DateTimeField(null=True, blank=True, default=timezone.now)
    time_end = models.DateTimeField(null=True, blank=True, default=timezone.now)
    title = models.TextField(blank=True, help_text="Session title to show on the Tour Schedule including time and tour type")
    session_note = models.TextField(blank=True)

    def __str__(self):
        return "Session (type: %s) from %s to %s" % (self.session_type, format_time(self.time_start), format_time(self.time_end))

    def get_key_id(self):
        return "%s_%s:%s" % (self.time_start.isoformat(), self.time_end.isoformat(), self.session_type) 

    @classmethod
    def get_key(cls, tour):
        return "%s_%s:%s" % (tour.time_start.isoformat(), tour.time_end.isoformat(), tour.tour_type)

    def get_title(self):
        return "%s - %s — %s" % (format_time(self.time_start), format_time(self.time_end), self.session_type)

    def to_json(self, with_related_data=True):
        data = {
            'id': self.id,
            'time_start': json_datetime(self.time_start),
            'time_end': json_datetime(self.time_end),
            'title': self.title or self.get_title(),
            'source_row_state': self.source_row_state,
        }

        if with_related_data:
            data.update({
                'tour_ids': list(self.tours.order_by('time_start', 'customer_name').values_list('id', flat=True)),
                'source_row_id': self.source_row_id,
                'field_auto_values': self.field_auto_values,
            })

        return data

class Tour(MutableDataRecord):
    MUTABLE_FIELDS = ('time_start', 'time_end',
        'tour_type', 'pickup_location', 'customer_name', 'customer_contact',
        'quantity', 'bikes', 'pax', 'notes', 'tour_area_id', 'session_id'
    )

    # database/metadata fields (not for user)
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, related_name='tours',
        help_text="Which session this tour is displayed under")

    # actual data fields used for computation
    time_start = models.DateTimeField(default=timezone.now, help_text="Tour start time (updated automatically)")
    time_end = models.DateTimeField(default=timezone.now, help_text="Tour end time (updated automatically)")
    tour_date = models.DateField(default=date.today, blank=True, null=True, help_text="Tour date (updated automatically)")
    tour_type = models.CharField(max_length=500, blank=True, help_text="Tour type (updated automatically)")

    # data/display fields
    pickup_location = models.TextField(blank=True, help_text="Pickup location as displayed on schedule (updated automatically)")
    customer_name = models.TextField(blank=True, help_text="Customer name as displayed on schedule (updated automatically)")
    customer_contact = models.TextField(blank=True, help_text="Customer contact telephone as displayed on schedule (updated automatically)")
    quantity = models.TextField(blank=True, help_text='Tour booking quantity as displayed on schedule (updated automatically)')

    # user fields
    bikes = models.JSONField(blank=True, default=dict, help_text="How many of each type of bike used for this tour. Edit this via the schedule")
    pax = models.PositiveIntegerField(blank=True, null=True, help_text="Number of people on the tour (if applicable)")
    notes = models.TextField(blank=True, help_text="Notes to show on tour, including any Booking Notes (not including venues)")
    show_venues = models.BooleanField(blank=True, default=True, help_text='Add automatic venue summary to notes if any venues are defined')

    tour_area = models.ForeignKey(Area, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return "%s %s (%s - %s)" % (self.time_start.date().isoformat(), self.tour_type, format_time(self.time_start), format_time(self.time_end))

    def duration(self):
        return format_timedelta(self.time_end - self.time_start)

    def is_cancelled(self):
        return self.source_row_state == 'deleted'

    def to_json(self, with_related_data=True):
        basic = {
            'id': self.id,
            'session_id': self.session_id,
            'time_start': json_datetime(self.time_start),
            'time_end': json_datetime(self.time_end),
            'tour_type': self.tour_type,
            'pickup_location': self.pickup_location,
            'customer_name': self.customer_name,
            'customer_contact': self.customer_contact,
            'quantity': self.quantity,
            'bikes': self.bikes,
            'pax': self.pax,
            'notes': self.notes,
            'show_venues': self.show_venues,
            'source_row_state': self.source_row_state,
        }

        if with_related_data:
            basic.update({
                'riders': [ tr.to_json() for tr in self.riders.order_by('-rider_role').all() ],
                'venues': [ tv.to_json() for tv in sorted(self.venues.all(), key=lambda v: v.time_arrive)],
                'source_row_id': self.source_row_id,
                'field_auto_values': self.field_auto_values,
            })
        return basic


RIDER_ROLES = {
    'lead': ('L', 'Tour Lead'),
    'colead': ('CL', 'Tour Co-lead'),
    'delegate': ('Del', 'Tour Delegator'),
    'team-lead': ('TL', 'Team Lead'),
    'noob': ('NOOB', 'Noob'),
    '': ('', 'Rider'),
}

class TourRider(MutableDataRecord):
    class Meta:
        verbose_name = 'Tour Rider (Advanced)'
        verbose_name_plural = 'Tour Riders (Advanced)'

    MUTABLE_FIELDS = ('rider_role', )

    #rider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    person = models.ForeignKey('Person', on_delete=models.CASCADE, null=True)
    tour = models.ForeignKey('Tour', on_delete=models.CASCADE, related_name='riders')
    # options: 'lead', 'colead', 'delegate', 'team-lead', 'noob'
    rider_role = models.CharField(max_length=100, blank=True)

    def display_role(self):
        return RIDER_ROLES[self.rider_role][1]

    def display_role_short(self):
        return RIDER_ROLES[self.rider_role][0]

    def __str__(self):
        return '%s: %s' % (str(self.tour), self.person.name)

    def to_json(self):
        return {
            'id': self.id,
            'tr_id': self.id,
            'rider_id': self.person_id,
            'tour_id': self.tour_id,
            'rider_role': self.rider_role,
            'rider_role_short': self.display_role_short(),
            'time_start': json_datetime(self.tour.time_start),
            'time_end': json_datetime(self.tour.time_end),
            'tour_type': self.tour.tour_type,
        }


class TourVenue(MutableDataRecord):
    class Meta:
        verbose_name = 'Tour Venue (Advanced)'
        verbose_name_plural = 'Tour Venues (Advanced)'

    MUTABLE_FIELDS = ('venue', 'time_arrive', 'time_depart', 'notes')
    ACTIVITY_CHOICES = [ (x, x) for x in ('venue', 'transit', 'activity')]

    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='tours', null=True, blank=True)
    tour = models.ForeignKey(Tour, on_delete=models.SET_NULL, null=True, related_name='venues')
    activity = models.CharField(blank=False, max_length=10, choices=ACTIVITY_CHOICES, default='venue')
    time_arrive = models.DateTimeField()
    time_depart = models.DateTimeField(null=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        if self.venue:
            return "%s: %s (%d mins)" % (
                self.time_arrive.strftime("%H:%M"),
                self.venue.name,
                (self.time_depart - self.time_arrive).total_seconds() // 60
            )
        else:
            return "%s: %s (%d mins)" % (
                self.time_arrive.strftime("%H:%M"), 
                self.activity, 
                (self.time_depart - self.time_arrive).total_seconds() // 60
            )

    def to_json(self):
        return {
            'id': self.id,
            'tour_id': self.tour_id,
            'venue_id': self.venue_id if self.venue else None,
            'activity': self.activity,
            'duration': (self.time_depart - self.time_arrive).total_seconds() // 60,
            'notes': self.notes,
            'field_auto_values': self.field_auto_values,
        }


