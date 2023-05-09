import re
import sys
import logging
import math
from peddleconcept.models import Tour, Session, ChangeLog
from peddleconcept.util import *
from peddleconcept.settings import *
from requests.utils import dict_from_cookiejar
from datetime import time, datetime
from django.utils import timezone, html
from django.utils.timezone import get_default_timezone
from django.template.loader import get_template
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from dateutil.parser import parse

from .rezdy_scraper import RezdyScraper
from .areas import load_areas_locations, get_tour_area, save_areas_locations

logger = logging.getLogger(__name__)

def get_rezdy_scraper():
    auth_config = get_login_setting(REZDY_LOGIN_SETTING)

    user = auth_config['login']['username']
    passwd = auth_config['login']['password']

    if not user:
        msg = "No Rezdy login credentials configured! Please adjust the Setting %s via the admin site." % SETTINGS_LOGIN
        logger.warning(msg)
        return None, msg

    last_cookies = get_setting(REZDY_COOKIES_SETTING)

    if last_cookies:
        cookies = last_cookies['cookiejar_dict']
    else:
        cookies = None

    return RezdyScraper(username=user, password=passwd, cookies=cookies), None

def rezdy_save_cookies(scraper):
    data = {
        'cookiejar_dict': dict_from_cookiejar(scraper.session.cookies),
    }
    set_setting(REZDY_COOKIES_SETTING, data)

QTY_REGEX = re.compile(r'^(?P<num>\d+) (?P<what>(?P<num2>\d)? ?[a-z0-9 &()]+|)$')
QTY_TERMS = {
    'solo': (1, 'bike'), # per bike
    'peddle': (1, 'bike'),
    'couple': (1, 'bike'),
    'regular': (1, 'bike'),
    'family': (1, 'ebike'), # also ebikes
    'ebike': (1, 'ebike'),
    'adult': (0.49, 'bike'), # per person
    'adults': (0.49, 'bike'),
    'person': (0.5, 'bike'),
    'people': (0.5, 'bike'),
    'quantity': (0.5, 'bike'),
    'child': (0.2501, 'bike'), # per child
    'children': (0.2501, 'bike'),
}

def get_bikes_from_quantity(qty_str):
    """
    Return number of bikes according to Rezdy order quantities
    eg. "1 Adult", "1 Solo Adult", "1 Couple", "1 Quantity", "1 Peddle", 
        "1 2 Adults & 1 Child (under 13)", "1 Family Ticket (See description below)"
    """
    # multiple lines are possible, treat them separately.
    qty = qty_str.split('\n')

    bikes = {}
    for line in qty_str.split('\n'):
        match = QTY_REGEX.match(line.lower())
        if not match:
            logger.error("cannot parse Quantity line: '%s' (%s)" % (line, e))
            continue
        
        num = int(match.group('num'))
        terms = match.group('what')
        if ' ' in terms:
            term = terms.split(' ')[0]
        else:
            term = terms
        
        if match.group('num2'): # assume per bike if there is a second number, eg. "1 2 adults & 1 child" => 1 bike
            bikes.setdefault('bike', 0)
            bikes['bike'] += num
        elif term in QTY_TERMS:
            bikes.setdefault(QTY_TERMS[term][1], 0)
            bikes[QTY_TERMS[term][1]] += num * QTY_TERMS[term][0]
        else:
            logger.warning("unknown Quantities term '%s' in '%s'" % (term, qty_line))
            return num
    # round up for all bikes - eg. for an adult + 2 children scenario with 0.9902 bikes
    for bike_type, num_bikes in bikes.items():
        bikes[bike_type] = math.ceil(num_bikes)

    return bikes

def parse_manifest_sessions(manifest_response):
    if not 'metadata' in manifest_response:
        return {}
    
    session_dict = {}
    for s in manifest_response['metadata']:
        id = html_unescape(s['id'])
        session_dict[id] = Session(
            source_row_id = id,
            source_row_state = 'live',
            source = 'rezdy',
            session_type = html_unescape(s['data'][1]).strip() if len(s['data']) >= 2 else '',
            session_note = html_unescape(s['data'][4]).strip() if len(s['data']) >= 6 else '',
        )

    for tour in manifest_response['data']:
        sess_id = tour['session-id']
        s = session_dict[sess_id]
        s.time_start = parse(tour['session-unformatted'])
        s.time_end = parse(tour['session-end-unformatted'])

    return session_dict

def parse_manifest_tours(manifest_response):
    tour_dict = {}
    for t in manifest_response['data']:
        time_start = parse(t['session-unformatted'])
        time_end = parse(t['session-end-unformatted'])
        quantity = html_unescape(t['quantities']).strip()
        booking_name = html_unescape(t['customer-full-name']).strip()

        # unbelievably, sometimes Rezdy spits out Double Escaped strings!
        if (cust_names := html_unescape(html_unescape(t['participants-list']))):
            cust_name = booking_name + '\n' + cust_names.replace(booking_name, '').replace('\n\n', '\n').strip()
        else:
            cust_name = booking_name

        order_id = "%s:%s" % (
            html_unescape(t['order-number']).strip(),
            t['order-item-id'],
        )
        pickup = html_unescape(t['pick-up-location']).strip()
        tour = Tour(
            source_row_id = order_id,
            source_row_state = 'live',
            source = 'rezdy',
            time_start = time_start,
            time_end = time_end,
            tour_type = html_unescape(t['product']).strip(),
            pickup_location = pickup,
            customer_name = cust_name,
            customer_contact = html_unescape(t['customer-phone']).strip(),
            quantity = quantity,
            bikes = get_bikes_from_quantity(quantity),
            notes = '\n'.join(( html_unescape(t[field]) for field in REZDY_NOTES_FIELDS )).strip(),
            tour_area = get_tour_area(pickup),
        )

        # extra attributes for processing only - not saved to DB
        tour.rezdy_order_id = t['order-number']
        tour.rezdy_session_id = t['session-id']

        tour_dict[order_id] = tour


    return tour_dict

@transaction.atomic
def update_from_rezdy(start_date, end_date, dry_run=False):
    """
    Fetches & accumulates tour/session data by querying Rezdy manifest for each day in the specified date range.
    Then updates all rows in the DB based on matching "Order Number + Order Item ID" with source_row_id
    Note that earlier tours were imported solely based on Order Number - need to also check and update these rows
    with the order item ID where possible.
    """
    time_start = datetime.now()
    log_msg = "begin Rezdy scan from %s to %s" % (start_date.isoformat(), end_date.isoformat())
    logger.info(log_msg)
    log = "%s - %s\n" % (time_start.isoformat(), log_msg)

    scraper, msg = get_rezdy_scraper()
    if not scraper:
        log += msg + '\n'
        return False, log
    
    load_areas_locations()

    rezdy_tours = {}
    rezdy_sessions = {}

    num_days = (end_date - start_date).days + 1
    num_days_ok = 0
    last_time = datetime.now()
    for day in range(num_days):
        day_date = add_days(start_date, day)
        manifest_resp = scraper.fetch_manifest_data(day_date)
        now = datetime.now()

        if not manifest_resp:
            log_msg = 'Rezdy manifest %s: scraper error: %s' % (day_date.isoformat(), scraper.get_last_error())
            logger.error(log_msg)
            log += log_msg + '\n'
            return False, log

        try:
            # convert manifest JSON data into Tour and Session instances
            # note these will have some extra attributes:
            # Tour.rezdy_session_id
            # Tour.rezdy_order_id
            tours = parse_manifest_tours(manifest_resp)
            sessions = parse_manifest_sessions(manifest_resp)
            rezdy_tours.update(tours)
            rezdy_sessions.update(sessions)
            log_msg = '%s: got %d tours, %d sessions in %0.1fs' % (
                day_date.isoformat(), len(tours), len(sessions), (now - last_time).total_seconds()
            )
            log += '%s\n' % log_msg
            logger.debug(log_msg)
            num_days_ok += 1
        except Exception as e:
            errormsg = 'Rezdy tour manifest for date %s returned error: %s' % (day_date.isoformat(), e)
            logger.error(errormsg)
            log += '%s\n' % errormsg
        last_time = now

        if num_days_ok == 1:
            rezdy_save_cookies(scraper)


    log_msg = "[%s : %s] Fetched %d tours, %d sessions for %d/%d days in %0.1fs" % (
        start_date.isoformat(), end_date.isoformat(), len(rezdy_tours),
        len(rezdy_sessions), num_days_ok, num_days, (datetime.now() - time_start).total_seconds()
    )
    logger.info(log_msg)
    log += '%s: %s\n' % (now.isoformat(), log_msg)
    scraper.close()

    date_filter = get_date_filter(start_date, end_date, 'time_start')

    # Tours and sessions: match rows from Rezdy with rows in DB
    db_sessions = {} # keyed by Rezdy session ID
    db_sessions_legacy = {} # keyed by legacy session key
    for s in Session.objects.filter(source='rezdy', **date_filter):
        if ':' in s.source_row_id:
            # session key format: will be updated if possible
            db_sessions_legacy[s.source_row_id] = s
        else:
            # Rezdy session ID
            db_sessions[s.source_row_id] = s

    num_legacy_orig = len(db_sessions_legacy)
    
    # identify and collect session-ids which are stored locally in the legacy format
    rezdy_sessions_matched = {} # dict of Rezdy Session ID to DB Session
    rezdy_sessions_added = {} # dict of Rezdy session-id to new Session instance
    for srid, s in rezdy_sessions.items():
        if (key := s.get_key_id()) in db_sessions_legacy:
            # update legacy source_row_id to new format
            s_legacy = db_sessions_legacy.pop(key)
            s_legacy.source_row_id = srid
            rezdy_sessions_matched[srid] = s_legacy
            db_sessions[srid] = s_legacy
        elif srid in db_sessions:
            rezdy_sessions_matched[srid] = db_sessions[srid]
        else:
            rezdy_sessions_added[srid] = s

    # find extra DB sessions to delete at the end
    db_sessions_not_matched = set(db_sessions.keys()) - set(rezdy_sessions_matched.keys())
    db_sessions_to_delete = list(db_sessions_legacy.values()) + list((db_sessions[srid] for srid in db_sessions_not_matched))
    log_msg = "merge sessions: to_delete=%d (legacy=%d), matched=%d (legacy=%d), added=%d" % (
        len(db_sessions_to_delete), len(db_sessions_legacy), len(rezdy_sessions_matched), num_legacy_orig - len(db_sessions_legacy),
        len(rezdy_sessions_added)
    )
    log += '%s: %s\n' % (datetime.now().isoformat(), log_msg)
    logger.info(log_msg)

    sessions_db = {} # keyed by Rezdy session-id not DB row ID!
    sessions_to_update = []
    changelogs = []
    for srid, dst_sess in rezdy_sessions_matched.items():
        src_sess = rezdy_sessions[srid]
        if (chglog := dst_sess.update_from_instance(src_sess)) is not None:
            changelogs.append(chglog)
            sessions_to_update.append(dst_sess)
        sessions_db[dst_sess.source_row_id] = dst_sess
    
    for sess in db_sessions_to_delete:
        if (chglog := sess.mark_source_deleted()):
            changelogs.append(chglog)
        sessions_to_update.append(sess)
    
    if not dry_run:
        sessions_updated = Session.objects.bulk_update(sessions_to_update,
            fields=[f.name for f in Session._meta.fields if not f.name == 'id'])
        sessions_unchanged = len(sessions_db) - sessions_updated
        sessions_created = Session.objects.bulk_create(rezdy_sessions_added.values())
        for new_sess in sessions_created:
            sessions_db[new_sess.source_row_id] = new_sess
            if (chglog := new_sess.mark_source_added()):
                changelogs.append(chglog)
        log_msg = "save sessions: added=%d, updated/cancelled=%d, cancelled=%d, unchanged=%d" % (
            len(sessions_created), sessions_updated, len(db_sessions_to_delete), sessions_unchanged
        )
    else:
        for new_sess in rezdy_sessions_added:
            sessions_db[new_sess.source_row_id] = new_sess
        log_msg = "dry run: no DB changes! sessions: added=%d, updated/cancelled=%d, cancelled=%d, unchanged=%d" % (
            len(rezdy_sessions_added), len(sessions_to_update), len(db_sessions_to_delete),
            len(sessions_db) - len(sessions_to_update)
        )
    log += '%s: %s\n' % (datetime.now().isoformat(), log_msg)
    logger.info(log_msg)    
    
    ## Tours
    rezdy_tours_all_possible_srids = {} # dict of Rezdy order number AND OrderNumber:OrderItemID to rezdy tour

    # search for tours by Source Row ID matching "added" tours: eg. if a tour is rescheduled to distant future,
    # it might already be in the DB, and isnt actually "new"
    for srid, t in rezdy_tours.items():
        rezdy_tours_all_possible_srids[t.rezdy_order_id] = t
        rezdy_tours_all_possible_srids[srid] = t

    db_tours_duplicate = []
    db_tours = {} # Tour rows with source_row_id='{order-number}:{order-item-id}'
    db_tours_legacy = {} # for legacy Tour rows with only order number
    for tour in Tour.objects.select_related('session').order_by('time_start').filter(
            Q(source='rezdy', **date_filter) | 
            Q(source='rezdy', source_row_id__in=rezdy_tours_all_possible_srids.keys())):
        # try to find duplicate tours here: keep only the LATEST copy
        if tour.source_row_id in db_tours_legacy:
            db_tours_duplicate.append(db_tours_legacy.pop(tour.source_row_id))
        if tour.source_row_id in db_tours:
            db_tours_duplicate.append(db_tours.pop(tour.source_row_id))

        if not ':' in tour.source_row_id:
            db_tours_legacy[tour.source_row_id] = tour
        else:
            order_number, _ = tour.source_row_id.split(':')
            if order_number in db_tours_legacy:
                db_tours_duplicate.append(db_tours_legacy.pop(order_number))
            db_tours[tour.source_row_id] = tour

    num_legacy_orig = len(db_tours_legacy)
    
    # reformat legacy tour source_row_ids into new ones - where they are available in Rezdy data
    rezdy_tours_added = {} # dict of Rezdy Tour ID to DB tour instance
    rezdy_tours_matched = {} # dict of Rezdy Tour ID to DB tour instance
    for srid, t in rezdy_tours.items():
        if (t_legacy := db_tours_legacy.get(t.rezdy_order_id)) and (
            t.tour_type.lower().strip() == t_legacy.tour_type.lower().strip()):
            t_legacy = db_tours_legacy.pop(t.rezdy_order_id)
            t_legacy.source_row_id = t.source_row_id # update the existing tour row source ID while we are here
            rezdy_tours_matched[srid] = t_legacy
        elif srid in db_tours:
            rezdy_tours_matched[srid] = db_tours[srid]
        else:
            if (chglog := t.mark_source_added()):
                changelogs.append(chglog)
            rezdy_tours_added[srid] = t
        t.session = sessions_db[t.rezdy_session_id]

    db_tours_not_matched = set(db_tours.keys()) - set(rezdy_tours_matched.keys())
    db_tours_to_delete = list(db_tours_legacy.values()) + list(db_tours[srid] for srid in db_tours_not_matched)

    log_msg = "merge tours: to_delete=%d (legacy=%d), matched=%d (legacy=%d), added=%d, duplicates=%d" % (
        len(db_tours_to_delete), num_legacy_orig, len(rezdy_tours_matched), num_legacy_orig - len(db_tours_legacy),
        len(rezdy_tours_added), len(db_tours_duplicate),
    )
    log += '%s: %s\n' % (datetime.now().isoformat(), log_msg)
    logger.info(log_msg)

    tours_to_update = []
    for srid, dst_tour in rezdy_tours_matched.items():
        src_tour = rezdy_tours[srid]
        if (chglog := dst_tour.update_from_instance(src_tour)) is not None:
            tours_to_update.append(dst_tour)
            changelogs.append(chglog)
            
    for tour in db_tours_to_delete:
        if (chglog := tour.mark_source_deleted()):
            changelogs.append(chglog)
        tours_to_update.append(tour)

    if not dry_run:
        num_updated = Tour.objects.bulk_update(tours_to_update,
            fields=[f.name for f in Tour._meta.fields if not f.name == 'id'])
        num_unchanged = len(db_tours) + num_legacy_orig - num_updated
        tours_created = Tour.objects.bulk_create(rezdy_tours_added.values())
        for tour in tours_created:
            if (chglog := tour.mark_source_added()):
                changelogs.append(chglog)
        new_changelogs = ChangeLog.objects.bulk_create(changelogs)
        save_areas_locations()

        log_msg = "save tours: added=%d, updated/cancelled=%d, cancelled=%d, unchanged=%d. Saved %d changelogs" % (
            len(tours_created), num_updated, len(db_tours_to_delete), num_unchanged, len(new_changelogs)
        )
    else:
        log_msg = "dry run: no DB changes! tours: added=%d, updated/cancelled=%d, cancelled=%d, unchanged=%d, changelogs=%d" % (
            len(rezdy_tours_added), len(tours_to_update), len(db_tours_to_delete), 
            len(db_tours) + num_legacy_orig - len(tours_to_update), len(changelogs)
        )
    log += '%s: %s\n' % (datetime.now().isoformat(), log_msg)
    logger.info(log_msg)

    return True, log