from django.db import transaction
import logging
import math
from peddleconcept.models import *
from peddleconcept.util import *
from peddleconcept.settings import *
from peddleconcept.deputy_api import DeputyAPI
from django.utils.timezone import localdate, localtime
from datetime import timedelta

logger = logging.getLogger(__name__)

def get_bikes_badges(bikes, bikeTypes):
    res = []
    for bike, qty in bikes.items():
        if not bike in bikeTypes or not qty:
            continue
        if not (bqty := bikeTypes[bike].get('quantity')):
            continue
        if bqty == qty and qty == 1:
            res.append('Needs %s' % bikeTypes[bike].get('name'))
        else:
            res.append('%d %s%s' % (
                qty,
                bikeTypes[bike].get('name'),
                's' if qty == 0 or qty > 1 else ''
            ))
    return res

def get_num_bikes(bikes):
    num_bikes = 0
    for bike_type_id, num in bikes.items():
        try:
            num = num or 0
            num_bikes += int(num)
        except ValueError:
            pass
    return num_bikes

def get_bikes_json(pax=0):
    return {
        'bike': math.ceil(pax / 2)
    }

def sum_bikes(bikes):
    """ count total number of bikes from tours in the session """
    total_bikes = {}
    for bk in bikes:
        for bid, num in bk.items():
            try:
                num = int(num)
            except TypeError:
                num = 0
            if bid in total_bikes:
                total_bikes[bid] += num
            else:
                total_bikes[bid] = num
    return total_bikes

def get_autoscan_status():
    scan_status = get_setting(AUTO_UPDATE_STATUS) or {}
    scan_config = get_setting(AUTO_UPDATE_SETTING) or {}
    scan_interval = int(scan_config.get('update_interval_minutes', 15))
    last_scan_begin = from_json_datetime(scan_status.get('last_update_begin', 0))
    last_scan = from_json_datetime(scan_status.get('last_update', 0))

    return last_scan_begin, last_scan, scan_interval

def get_venues_summary(tour):
    venues = list(tour.venues.all())
    if len(venues) == 0:
        return
    venues.sort(key=(lambda tv: tv.time_arrive))

    """
	"venues": [
			"venue_id": null,
			"activity": "transit",
			"duration": 15,
			"notes": "",
		},
			"venue_id": 2,
			"activity": "venue",
			"duration": 30,
			"notes": "[$12 neon margarita]",
		},
			"venue_id": null,
			"activity": "activity",
			"duration": 60,
			"notes": "proceed to Russell Square for G RATED scav",
		},
			"venue_id": null,
			"activity": "transit",
			"duration": 15,
			"notes": "Finish scav @ Russell, tally & present prize",
		},
			"venue_id": 6,
			"activity": "venue",
			"duration": 15,
			"notes": "[25% off first round]",
	]
    5:00pm - Tour start
    5:15pm - Arrive Neon Palms [$12 neon margarita]
    5:45pm - Leave NP, proceed to Russell Square for G RATED scav
    6:30pm - Finish scav @ Russell, tally & present prize
    6:45pm - Arrive Planet Royale [25% off first round]
    7:00pm - Tour fin
    """
    vsum = ["%s - Tour start" % format_time(tour.time_start)]
    prev = None
    for i in range(len(venues)):
        tv = venues[i]
        if tv.activity == 'transit':
            if tv.notes:
                if prev and prev.activity == 'venue':
                    vsum[-1] += ". %s" % tv.notes
                else:
                    vsum.append("%s - %s" % (format_time(tv.time_arrive), tv.notes))
        elif tv.activity == 'venue' or tv.activity == 'activity':
            if tv.venue:
                if tv.notes:
                    notes = tv.notes if tv.notes.startswith('[') else " - %s" % tv.notes
                    vsum.append("%s - Arrive %s %s" % (format_time(tv.time_arrive), tv.venue.name, notes))
                else:
                    vsum.append("%s - Arrive %s" % (format_time(tv.time_arrive), tv.venue.name))
                if i < len(venues) - 1:
                    vsum.append("%s - Depart %s" % (format_time(tv.time_depart), abbreviate(tv.venue.name)))
            else:
                if prev and prev.activity == 'venue':
                    vsum[-1] += ", %s" % tv.notes
                else:
                    vsum.append("%s - %s" % (format_time(tv.time_arrive), tv.notes))
        prev = tv

    vsum.append("%s - Tour finish" % format_time(tv.time_depart))
    return '\n'.join(vsum)

def get_rider_schedule(start_date, end_date, person):
    """ prepare data for RiderTourSchedule """
    # get data for 2 days prior up to 2 weeks after

    tr_filter = get_date_filter(start_date, end_date, 'tour__time_start')
    tour_rider_qs = TourRider.objects.select_related(
        'tour', 'tour__session', 'person'
    ).prefetch_related(
        'tour__riders', 'tour__venues'
    ).filter(
        person=person, **tr_filter
    ).order_by('tour__time_start')

    trs_by_date = {}
    for tr in tour_rider_qs:
        key_date = json_datetime(localdate(tr.tour.time_start))
        trs_for_date = trs_by_date.setdefault(key_date, [])
        trs_for_date.append({
            'tour': tr.tour.to_json(with_related_data=True, in_editor=False),
            'session': tr.tour.session.to_json(in_editor=False),
            'tourRider': tr.to_json(),
        })

    return {
        'tour_dates': trs_by_date,
        'tourAreas': {
            area.id: area.to_json() for area in Area.objects.filter(active=True)
        },
        'riders': {
            r.id: r.display_name or r.name for r in Person.objects.filter(rider_class__isnull=False)
        },
        'bikeTypes': get_bikes_setting(),
        'venues': { v.id: v.to_json() for v in Venue.objects.all() },
        'startDate': json_datetime(start_date),
        'endDate': json_datetime(end_date),
    }

def get_tour_schedule_data(tour_area, tours_date, in_editor=False):
    """ prepare data for TourScheduleEditor """
    date_filter = get_date_filter(tours_date, tours_date, 'time_start')
    tours_qs = Tour.objects.filter(
        tour_area = tour_area,
        **date_filter
    ).order_by(
        'time_start', 'tour_type', 'customer_name'
    ).prefetch_related('riders', 'venues').select_related('session')

    all_people = Person.objects.in_bulk()
    # include only riders ON schedule ( + active riders not on schedule - for editor only)
    sched_riders = set() 

    # accumulate only sessions which have tours & tours json at the same time
    session_order = [] # list of session IDs in order
    sessions_with_tours_json = {} # dict of session ID to session data
    tours_json = {} # dict of tour ID to tour data

    for t in tours_qs:
        tours_json[t.id] = t.to_json(with_related_data=True, in_editor=in_editor)
        if not t.session_id in sessions_with_tours_json:
            session_order.append(t.session_id)
            sess_json = sessions_with_tours_json[t.session_id] = t.session.to_json()
            sess_json['tour_ids'] = []
        else:
            sess_json = sessions_with_tours_json[t.session_id]
        # build a list of tour IDs for each session, preserving ordering
        sess_json['tour_ids'].append(t.id)
        for tr in t.riders.all():
            sched_riders.add(tr.person_id)
    
    if in_editor:
        # add any active riders not on schedule
        for r_id, r in all_people.items():
            if r.active and r.rider_class:
                sched_riders.add(r_id)

    data = {
        'sessions': sessions_with_tours_json,
        'tours': tours_json,
        'session_order': session_order,
        'riders': {
            r_id: all_people[r_id].to_json(in_editor=in_editor)
            for r_id in sched_riders
        },
        'venues': {
            v.id: v.to_json() for v in Venue.objects.all()
        },
        'venue_presets': get_venues_presets(),
        'bike_types': get_bikes_setting(),
        'tours_date': json_datetime(tours_date),
        'tours_date_formatted': tours_date.strftime("%a %d/%m"),
    }

    return data

def get_rider_time_off_json(tours_date):
    rider_times_off = get_rider_unavailability(tours_date)
    unavail_json = {}
    for r_id, times_off in rider_times_off.items():
        t_json = unavail_json[r_id] = []
        for ts in times_off:
            t_json.append({
                'start': json_datetime(ts[0]),
                'end': json_datetime(ts[1]),
                #'comment': ts[2],
                'tour_id': ts[3] if len(ts) == 4 else None,
            })

    return unavail_json

def get_tour_summary(start_date, end_date):
    """ returns a list of tours with type, quantity/pax, bikes, num. riders needed/allocated """
    date_filter = get_date_filter(start_date, end_date, 'time_start')
    tours_qs = Tour.objects.prefetch_related('riders').select_related('tour_area').filter(
        **date_filter,
    ).order_by('tour_area__sort_order', 'time_start', 'tour_type')

    tours_by_date = {} # dict of iso dates with data on tours
    tours_ordered = [] # same dict instances added to a list in order

    bike_types = get_bikes_setting()

    for t in tours_qs:
        date = t.time_start.date().isoformat()
        if not date in tours_by_date:
            today = tours_by_date[date] = {
                'areas': {},
                'date': json_datetime(t.time_start.date()),
                'isodate': date,
                'updated': 0,
            }
            tours_ordered.append(today)
        else:
            today = tours_by_date[date]
        
        # count tour info by area within each day
        if not t.tour_area_id in today['areas']:
            today_area = today['areas'][t.tour_area_id] = { # areaInfo in TourDashboard.jsx
                'cancelled': 0,
                'needs_riders': 0,
                'filled': 0,
                'tours': [],
                'area_id': t.tour_area_id,
            }
        else:
            today_area = today['areas'][t.tour_area_id]

        num_riders = len(t.riders.all())
        num_bikes = get_num_bikes(t.bikes)
        canned = t.is_cancelled()
        if canned:
            today_area['cancelled'] += 1
        elif num_riders < num_bikes:
            today_area['needs_riders'] += 1
        else:
            today_area['filled'] += 1

        tour_updated = json_datetime(t.updated)
        if tour_updated > today['updated']:
            today['updated'] = tour_updated

        today_area['tours'].append({
            'id': t.id,
            'num_riders': num_riders,
            'num_bikes': num_bikes,
            'time_start': json_datetime(t.time_start),
            'time_end': json_datetime(t.time_end),
            'tour_type': t.tour_type,
            'quantity': t.quantity,
            'cancelled': canned,
        })

    return tours_ordered

def get_tour_rosters(tours_date, area):
    """ Generate Roster instances for the tour schedule for given date/area """
    setup_time_mins = get_setting_or_default('warehouse_setup_time_minutes', 45)

    tour_riders = TourRider.objects.filter(
        **get_date_filter(tours_date, tours_date, 'tour__time_start'),
        tour__tour_area = area,
        person__source_row_state='live',
        person__source_row_id__isnull=False,
    ).select_related('tour', 'tour__tour_area', 'person').order_by(
        'tour__time_start',
    )

    riders_by_srid = {}
    rider_tours = {}
    for tr in tour_riders:
        tours_list = rider_tours.setdefault(tr.person.source_row_id, [])
        tours_list.append(tr)
        riders_by_srid[tr.person.source_row_id] = tr.person
    
    # generate shift/roster data based on ordered list of TourRiders for each rider
    rosters = []

    for person_srid, tr_list in rider_tours.items():
        # adapted algorithm from generate_pay_slots()

        # add setup time
        start_time = tr_list[0].tour.time_start - timedelta(minutes=setup_time_mins)
        my_roster_slots = [{
            'type': 'break',
            'description': 'Setup time',
            'time_start': json_datetime(start_time),
            'time_end': json_datetime(tr_list[0].tour.time_start),
        }]
        my_roster_notes = [
            '%s: Setup at WH' % format_time(start_time),
        ]

        end_time = tr_list[-1].tour.time_end

        prev_tr = None
        for tr in tr_list:
            if prev_tr is not None:
                my_roster_slots.append({
                    'type': 'break',
                    'description': 'Tour break',
                    'time_start': json_datetime(prev_tr.tour.time_end),
                    'time_end': json_datetime(tr.tour.time_start),
                })
                my_roster_notes.append(
                    '%s: %d minute break' % (
                        format_time(prev_tr.tour.time_end),
                        (tr.tour.time_start - prev_tr.tour.time_end).total_seconds() // 60,
                    )
                )
            my_roster_slots.append({
                'type': 'tour',
                'time_start': json_datetime(tr.tour.time_start),
                'time_end': json_datetime(tr.tour.time_end),
                'description': tr.tour.tour_type,
                'tour_id': tr.tour_id,
            })
            my_roster_notes.append(
                '%s: %s (%d minutes)' % (
                    format_time(tr.tour.time_start),
                    tr.tour.tour_type,
                    (tr.tour.time_end - tr.tour.time_start).total_seconds() // 60,
                )
            )
            prev_tr = tr

        my_roster_notes.append('%s: Finish' % format_time(end_time))

        roster = Roster(
            source = 'auto',
            person = riders_by_srid[person_srid],
            area = area,
            time_start = start_time,
            time_end = end_time,
            tour_slots = my_roster_slots,
            shift_notes = '\n'.join(my_roster_notes),
        )
        rosters.append(roster)

    logger.info("Generated %d rosters for tours in area %s on date %s" % (
        len(rosters), area.name, tours_date.isoformat(),
    ))
    return rosters


def save_tour_schedule(tours_date, schedule_data):
    # get the tours and sessions in a dict keyed by id
    date_filter = get_date_filter(tours_date, tours_date, 'time_start')
    tours = Tour.objects.filter(**date_filter).prefetch_related('venues', 'riders').in_bulk()
    sessions = Session.objects.filter(**date_filter).in_bulk()
    riders = Person.objects.in_bulk()
    venues = Venue.objects.in_bulk()

    related_date_filter = get_date_filter(tours_date, tours_date, 'tour__time_start')

    #print(tours)
    #print(schedule_data)
    with transaction.atomic():
        for tour_id, t in schedule_data.get('tours', {}).items():
            tour = tours.get(int(tour_id))
            if not tour:
                continue

            # group by Rider (enforce unique TourRider per tour)
            my_riders = {
                tr.person.id: tr for tr in tour.riders.all()
            }
            tour_riders_updated_ids = set() # by TourRider ID
            tour_riders_existing_ids = set((tr.id for tr in tour.riders.all()))
        
            for tr_json in t.get('riders', []):
                rider = riders.get(int(tr_json.get('rider_id')))
                if not rider:
                    continue
                elif rider.id in my_riders:
                    # update existing row, based on existing rider ID (can't have duplicate TourRiders per rider per tour)
                    tr = my_riders[rider.id]
                else:
                    # No existing tour rider
                    tr = None

                if not tr:
                    # create new TourRider
                    tr = TourRider(
                        person = rider,
                        tour = tour,
                        rider_role = tr_json.get('rider_role') or '',
                    )
                    tr.save()
                else:
                    # update existing TourRider
                    tr.rider_role = tr_json.get('rider_role') or ''
                    tr.save()
                    tour_riders_updated_ids.add(tr.id)
                my_riders[rider.id] = tr

            tr_ids_deleted = tour_riders_existing_ids - tour_riders_updated_ids
            for tr_id in tr_ids_deleted:
                my_riders[tr_id].delete()

            my_venues = {
                tv.id: tv for tv in tour.venues.all()
            }
            my_tourvenues_existing = set(my_venues.keys())
            my_tourvenues_now = set()
            time_arrive = tour.time_start
            for tv_json in t.get('venues', []):
                tvid = tv_json.get('id')
                tv = my_venues.get(int(tvid)) if tvid is not None else None
                venue_id = tv_json.get('venue_id')
                
                if not tv:
                    # create new TourVenue
                    tv = TourVenue(
                        tour_id = tour.id,
                    )
                
                tv.activity = tv_json.get('activity')
                tv.time_arrive = time_arrive
                tv.time_depart = time_arrive + timedelta(minutes=int(tv_json.get('duration')))
                tv.notes = tv_json.get('notes')
                tv.venue_id = int(venue_id) if venue_id else None
                tv.save()

                my_tourvenues_now.add(tv.id)
                
                time_arrive = tv.time_depart

            # delete leftover TourVenues
            tvs_deleted = my_tourvenues_existing - my_tourvenues_now
            for tv_id in tvs_deleted:
                my_venues[tv_id].delete()
        
            # update tour itself
            for field in ('customer_name', 'customer_contact', 'quantity', 'pickup_location', 'bikes', 'notes'):
                tour.update_field(field, t.get(field), 'user')
            tour.save()

        for sess_id, sess_json in schedule_data.get('sessions', {}).items():
            sess = sessions.get(int(sess_id))
            if not sess:
                continue

            if sess.tours.count() == 0:
                # delete empty sessions on save
                sess.delete()
            else:
                sess.title = sess_json['title']
                sess.save()

def get_venues_report(start_date, end_date):
    """
    Generate a report of required venue bookings for a particular week. Group by venues,
    include date/time, num pax per booking timeslot 
    """

    tour_bookings = TourVenue.objects.select_related('tour', 'venue').filter(
            venue__isnull=False,
            **get_date_filter(start_date, end_date, 'tour__time_start'),
        ).order_by(
            'venue__name', 'time_arrive'
        )

    venues = {}
    for tv in tour_bookings:
        # group by venue overall
        venue = venues.setdefault(tv.venue.id, {
            **tv.venue.to_json(),
            'booking_dates': {},
        })

        # keep track of total number of pax, also what pax in different groups/tours
        # here we group by timespan as well (eg. one booking per timespan per venue)
        # also, group by date per venue
        tour_date = localdate(tv.tour.time_start)
        vdate = venue['booking_dates'].setdefault(tour_date, {
            'date': json_datetime(tour_date),
            'times': {},
        })
        
        time_key = "%s-%s" % (
            localtime(tv.time_arrive).isoformat(),
            localtime(tv.time_depart).isoformat(),
        )

        vt = vdate['times'].setdefault(time_key, {
            'tours': [], # tuples of (tour_type, quantity, pax)
            'time_arrive': json_datetime(tv.time_arrive),
            'duration': (tv.time_depart - tv.time_arrive).total_seconds() // 60,
            'time_depart': json_datetime(tv.time_depart),
        })

        vt['tours'].append({
            'tour_type': tv.tour.tour_type,
            'quantity': tv.tour.quantity,
        })

    # simplify to array of bookings per venue
    for venue_id, venue in venues.items():
        venue['booking_dates'] = sorted(venue['booking_dates'].values(), key=lambda b: b['date'])
        for vdate in venue['booking_dates']:
            vdate['times'] = sorted(vdate['times'].values(), key=lambda vt: vt['time_arrive'])

    return venues

def get_rider_unavailability(tours_date):
    """ query Deputy API and tour schedules to determine rider availability on the given date """
    api = DeputyAPI()

    deputy_riders = {
        r.source_row_id: r
        for r in Person.objects.filter(
            active=True, rider_class__isnull=False,
            source='deputy', source_row_id__isnull=False, source_row_state='live',
        )
    }

    tour_riders = TourRider.objects.select_related('tour').filter(
        **get_date_filter(tours_date, tours_date, 'tour__time_start')
    )

    try:
        dpt_employee_time_off = api.query_leave_unavailability(tours_date)
        rider_unavail = {}
        for emp_id, emp_time in dpt_employee_time_off.items():
            if not emp_id in deputy_riders:
                logger.warning("Unavailable Deputy employee id %s not found among active riders in DB" % emp_id)
                continue
            rider_unavail[deputy_riders[emp_id].id] = emp_time
    except Exception as e:
        logger.error("Error processing Deputy unavailabilities: %s: %s" % (type(e).__name__, str(e)))
        rider_unavail = {}
    
    for tr in tour_riders:
        emp_time = rider_unavail.setdefault(tr.person_id, [])
        emp_time.append(
            ( tr.tour.time_start, tr.tour.time_end, 'already on tours', tr.tour.id )
        )
    
    return rider_unavail
