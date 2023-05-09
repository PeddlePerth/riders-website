from django.conf import settings
from django.contrib import messages 
from django.utils.timezone import make_aware, get_default_timezone
from django.db import transaction
from datetime import datetime, timedelta
from peddleconcept.util import format_timedelta, update_model_with_dict, get_date_filter
from peddleconcept.models import Tour, Session, Settings, ChangeLog
from peddleconcept.settings import *
import math
import logging

from requests.utils import dict_from_cookiejar

from .red61_scraper import Red61Scraper
from .schedules import get_bikes_json
from .areas import load_areas_locations, get_tour_area, save_areas_locations

logger = logging.getLogger(__name__)


fringe_event_details = {
    'Adults Scavenger Hunt': {
        'duration': timedelta(minutes=60),
        'pickup_location': 'Russel Square (Pleasure Gardens)',
    },
    'The Fringe Bar Tour': {
        'duration': timedelta(minutes=120),
        'pickup_location': 'Yagan Square (Digital Tower)',
    },
    'Experience Perth Family Tour': {
        'duration': timedelta(minutes=90),
        'pickup_location': 'Russel Square (Pleasure Gardens)',
    },
    'default': {
        'duration': timedelta(minutes=60),
        'pickup_location': '',
    }
}

def get_fringe_scraper():
    auth_config = get_login_setting(FRINGE_LOGIN_SETTING)

    user = auth_config['login']['username']
    passwd = auth_config['login']['password']

    if not user:
        return None, "No Fringe/Red61 login credentials configured! Please adjust the setting %s in the admin site." % FRINGE_LOGIN_SETTING

    last_cookies = get_setting(FRINGE_COOKIES_SETTING)
    if last_cookies:
        cookies = last_cookies['cookiejar_dict']
    else:
        cookies = None

    scraper = Red61Scraper(username=user, password=passwd, cookies=cookies)
    return scraper, None

@transaction.atomic
def update_from_fringe(start_date, end_date, dry_run=False):
    """ returns a list of Tour objects from the given date's Fringe bookings """
    time_start = datetime.now()
    scraper, msg = get_fringe_scraper()
    log_msg = "begin Fringe scan from date %s to %s" % (start_date.isoformat(), end_date.isoformat())
    log = "%s - %s\n" % (time_start, log_msg)
    logger.info(log_msg)

    if not scraper:
        log_msg = 'Scraper error: %s' % msg
        logger.error(log_msg)
        log += log_msg + '\n'
        return False, log

    if not scraper.try_login():
        log_msg = 'Bad login to Fringe/Red61, check the %s setting in the Admin Site' % FRINGE_LOGIN_SETTING
        log += log_msg + '\n'
        logger.error(log_msg) 
        return False, log

    fringe_ticket_data = scraper.run_seats_report(start_date, end_date)
    scraper.session.close()
    scan_time = datetime.now() - time_start

    # save cookies for next time - skip login
    set_setting(FRINGE_COOKIES_SETTING, {
        'cookiejar_dict': dict_from_cookiejar(scraper.session.cookies),
    })

    if fringe_ticket_data is None:
        log_msg = 'Error retrieving Fringe tickets report from Red61 (%0.1fs)' % scan_time.total_seconds()
        log += log_msg + '\n'
        logger.error(log_msg)
        return False, log
    elif not fringe_ticket_data:
        return True, 'No Fringe tickets for dates %s to %s (%0.1fs)' % (
            start_date.isoformat(), end_date.isoformat(), scan_time.total_seconds())

    load_areas_locations()

    tours = {} # keyed by "{performance ID}"
    for ticket in fringe_ticket_data:
        # create a single tour row per timeslot per tour type, eg. one tour per session
        tour_key = ticket['performance']
        customer_name = " ".join(ticket['customer_name'].split(", ")[::-1])
        
        tour_notes = "%s: %s" % (customer_name, ticket['access_information']) if ticket['access_information'] else None
        
        if not tour_key in tours:
            # add new tour for this performance ID
            event_deets = fringe_event_details.get(ticket['event_title'], fringe_event_details['default'])

            time_start = datetime.strptime(ticket['perf_date'], "%Y-%m-%d %H:%M")
            time_end = time_start + event_deets['duration']

            tours[tour_key] = {
                # important data fields
                'source_row_id': tour_key,
                'source_row_state': 'live',
                'source': 'fringe',
                'time_start': make_aware(time_start),
                'time_end': make_aware(time_end),
                'tour_type': "FRINGE %s" % ticket['event_title'],
                
                # human data fields
                'pickup_location': event_deets['pickup_location'],

                # user fields, best-guess calculations
                # store some temporary data for later aggregation
                'customer_name': {
                    customer_name: 1,
                },
                'notes': [ tour_notes ] if tour_notes else [],
            }
        else:
            # add another booking to the already-seen tour
            t = tours[tour_key]
            num_booked = t['customer_name'].get(customer_name, 0)
            t['customer_name'][customer_name] = num_booked + 1

            if tour_notes:
                t['notes'].append(tour_notes)

    log_msg = 'Parsed %d Fringe tours from %d tickets' % (len(tours), len(fringe_ticket_data))
    log += log_msg + '\n'
    logger.info(log_msg)
    
    # Look up Tour and Session instances in DB
    date_filter = get_date_filter(start_date, end_date, 'time_start')
    db_tours = {
        tour.source_row_id: tour for tour in Tour.objects.filter(source='fringe', **date_filter)
    }
    db_sessions = {
        sess.source_row_id: sess for sess in Session.objects.filter(source='fringe', **date_filter)
    }

    # heuristic for checking Fringe report failures
    if len(db_tours) > 0 and len(db_sessions) > 0 and len(fringe_ticket_data) == 0:
        log_msg = 'No fringe tickets when existing tours/sessions found. Aborting due to likely Red61 system fault.'
        logger.warning(log_msg)
        log += log_msg + '\n'
        return False, log

    changelogs = [] # keep track of row-by-row changes with ChangeLog instances

    # construct Tour model instances for each tour + a corresponding Session object
    tour_rows_matched = set() # keyed by source_row_id
    tours_to_add = []
    tours_to_update = []
    session_rows_matched = set()
    sessions_to_add = []
    sessions_to_update = []

    for t in tours.values():
        names = []
        total_num = 0
        for customer, num in t['customer_name'].items():
            total_num += num
            names.append('%s (%d)' % (customer, num))
        t['customer_name'] = '\n'.join(names)
        t['notes'] = '\n'.join(t['notes'])

        # source rows for Tour and Session: directly based on Fringe data
        tour_src = Tour(
            customer_contact = 'N/A',
            pax = total_num,
            bikes = get_bikes_json(total_num),
            quantity = "%d Attendee%s" % (total_num, 's' if total_num > 1 else ''),
            **t,
            tour_area = get_tour_area(t['pickup_location']),
        )

        sess_src = Session(
            source_row_id = tour_src.source_row_id,
            source_row_state = 'live',
            source = 'fringe',
            time_start = tour_src.time_start,
            time_end = tour_src.time_end,
            session_type = tour_src.tour_type,
        )

        # match and update session, or create new session if none found
        fringe_src_id = tour_src.source_row_id
        if fringe_src_id in db_sessions:
            sess = db_sessions[fringe_src_id]
            tour_src.session = sess
            session_rows_matched.add(fringe_src_id)
            if (chglog := sess.update_from_instance(sess_src)) is not None:
                changelogs.append(chglog)
                sessions_to_update.append(sess)
        else:
            # no existing session found - use new instance
            tour_src.session = sess_src
            sessions_to_add.append(sess_src)
        
        # match/update or create new tour
        if fringe_src_id in db_tours:
            tour = db_tours[fringe_src_id]
            tour_rows_matched.add(fringe_src_id)
            if (chglog := tour.update_from_instance(tour_src)) is not None:
                changelogs.append(chglog)
                tours_to_update.append(tour)
        else:
            # no existing tour - use the new one
            tours_to_add.append(tour_src)

    sessions_to_delete = set(db_sessions.keys()) - session_rows_matched
    for srid in sessions_to_delete:
        sess = db_sessions[srid]
        if chglog := sess.mark_source_deleted():
            changelogs.append(chglog)
        sessions_to_update.append(sess)
    
    if not dry_run:
        sessions_created = Session.objects.bulk_create(sessions_to_add)
        for s in sessions_created:
            if (chglog := s.mark_source_added()):
                changelogs.append(chglog)
        sessions_updated = Session.objects.bulk_update(sessions_to_update, 
            fields=[f.name for f in Session._meta.fields if not f.name == 'id'])
        log_msg = "save sessions: added=%d, updated/cancelled=%d, cancelled=%d, unchanged=%d" % (
            len(sessions_created), sessions_updated, len(sessions_to_delete),
            len(db_sessions) - sessions_updated
        )
    else:   
        log_msg = "dry run: no DB changes! sessions: added=%d, updated/cancelled=%d, cancelled=%d, unchanged=%d" % (
            len(sessions_to_add), len(sessions_to_update), len(sessions_to_delete), len(db_sessions) - len(sessions_to_update)
        )
    logger.info(log_msg)
    log += log_msg + '\n'
    
    tours_to_delete = set(db_tours.keys()) - tour_rows_matched
    for srid in tours_to_delete:
        tour = db_tours[srid]
        if (chglog := tour.mark_source_deleted()):
            changelogs.append(chglog)
        tours_to_update.append(tour)
    
    if not dry_run:
        tours_created = Tour.objects.bulk_create(tours_to_add)
        for t in tours_created:
            if (chglog := t.mark_source_added()):
                changelogs.append(chglog)
        tours_updated = Tour.objects.bulk_update(tours_to_update,
            fields=[f.name for f in Tour._meta.fields if not f.name == 'id'])
        new_changelogs = ChangeLog.objects.bulk_create(changelogs)
        log_msg = "save tours: added=%d, updated/cancelled=%d, cancelled=%d, unchanged=%d, changelogs=%d" % (
            len(tours_created), tours_updated, len(tours_to_delete), len(db_tours) - tours_updated, len(new_changelogs)
        )
        save_areas_locations()
    else:
        log_msg = "dry run: no DB changes! tours: added=%d, updated/cancelled=%d, cancelled=%d, unchanged=%d, changelogs=%d" % (
            len(tours_to_add), len(tours_to_update), len(tours_to_delete), len(db_tours) - len(tours_to_update), len(changelogs)
        )
    logger.info(log_msg)
    log += log_msg + '\n'

    return True, log
