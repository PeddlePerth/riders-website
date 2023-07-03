from django.db import transaction
from django.utils.timezone import localdate, localtime
import logging
import math
from .models import *
from .util import *
from .settings import *

def get_tour_pay_config():
    pay_config = get_setting(TOUR_PAY_SETTING) or {}
    
    tour_types_qs = Tour.objects.all().order_by('tour_type')

    pay_config.setdefault('roles', {})
    pay_config.setdefault('tour_types', {})

    # ensure pay config is fully up to date with actual tours
    for role_id, role in RIDER_ROLES.items():
        if role_id == '':
            continue
        if not isinstance(pay_config['roles'].get(role_id), dict):
            pay_config['roles'][role_id] = {}
        
        pay_config['roles'][role_id].setdefault('pay_rate', 35 if 'lead' in role_id else 30)
        pay_config['roles'][role_id]['title'] = "%s (%s)" % (role[1], role[0])


    for tour in tour_types_qs:
        if 'custom' in tour.tour_type.lower():
            continue # ignore "Custom Tour" and the like
        
        if not isinstance(pay_config['tour_types'].get(tour.tour_type), dict):
            tt = pay_config['tour_types'][tour.tour_type] = {}
        else:
            tt = pay_config['tour_types'][tour.tour_type]
        
        tt.setdefault('pay_rate', 30)
        tt.setdefault('paid_duration_mins', (tour.time_end - tour.time_start).total_seconds() // 60)
    
    set_setting(TOUR_PAY_SETTING, pay_config)

    pay_config['rider_pay_rates'] = {
        p.id: p.override_pay_rate for p in Person.objects.filter(override_pay_rate__isnull=False)
    }

    pay_config.setdefault('max_total_break_mins', 60) # more than 60 minutes of break time per day will be ignored (haha)
    pay_config.setdefault('daily_unpaid_break_mins', 30) # will set a particular break time as unpaid)
    pay_config.setdefault('time_before_unpaid_break', 60*5) # how long cumulatively before every possible break time becomes unpaid
    pay_config.setdefault('min_daily_mins', 150) # minumum minutes paid for the day
    pay_config.setdefault('default_rate', 30) # default pay rate
    pay_config.setdefault('break_pay_rate', 0) # use a specific pay rate for paid break time
    pay_config.setdefault('paid_break_max_len', 15) # all breaks under 15 minutes are to be paid to riders

    return pay_config

def save_tour_pay_config(pay_config):
    #for f in ('max_total_break_mins', 'default_paid_break_mins', 'daily_unpaid_break_mins', 'min_daily_mins'):
    conf = {}
    for f in (
        'max_total_break_mins',
        'daily_unpaid_break_mins',
        'min_daily_mins',
        'time_before_unpaid_break',
        'default_rate',
        'break_pay_rate',
        'paid_break_max_len'):
        conf[f] = int(pay_config.get(f, 0))

    set_setting(TOUR_PAY_SETTING, conf)

def get_pay_rate(pay_config, tour_rider):
    """ returns the _default_ hourly pay rate for a given TourRider along with a reason """

    # Rider pay rate takes precedence
    if tour_rider.person.override_pay_rate:
        return (tour_rider.person.override_pay_rate, 'Fixed rider rate')

    rider_rate = tour_rider.person.pay_rate()
    if rider_rate:
        return (rider_rate, tour_rider.person.rider_class_label())

    # fall back to defailt rate
    return (
        pay_config.get('default_rate', 30),
        'Default rate'
    )
    


def generate_tour_pay_slots(start_date, end_date, pay_config):
    """
    Make some PaySlot instances for each Rider's scheduled TourRiders and break times for the pay period.
    Returns a list of RiderPaySlots.

    post-processing: update paid break times
    maximise to daily unpaid break time
    
    enforce minimum pay time
    """
    tour_riders = TourRider.objects.select_related('tour', 'person', 'tour__session').filter(
        **get_date_filter(start_date, end_date, 'tour__time_start')
    ).order_by('person__id', 'tour__time_start')

    # Group TourRiders by Rider, as lists of tours per day
    riders_tours = {}
    day = None
    last_rider = None
    for tr in tour_riders:
        # for each rider ID, store the TourRiders in time order
        if (today := tr.tour.time_start.date()) != day or last_rider != tr.person:
            tours_today = []
            riders_tours.setdefault(tr.person.id, []).append(tours_today)
            day = today
            
        tours_today.append(tr)
        last_rider = tr.person

    time_before_unpaid_break = pay_config.get('time_before_unpaid_break', 100000)
    daily_unpaid_break_mins = pay_config.get('daily_unpaid_break_mins', 30)
    min_daily_mins = pay_config.get('min_daily_mins', 0) # give me this day my daily minute
    break_pay_rate = pay_config.get('break_pay_rate', 0)
    paid_break_max = pay_config.get('paid_break_max_len', 0)
    tour_types_seen = set()

    pay_slots = []
    # process one rider at a time
    for rider_id, tours_days in riders_tours.items():
        for tours_today in tours_days:
            # don't roll-over from one day to the next, break slots are only inserted _in between_ tours on the same day
            # cumulative statistics for each rider-day
            my_pay_slots = []
            my_total_mins = 0 # total paid time (mins)
            my_total_break = 0 # total paid break time (mins)
            my_unpaid_break = 0 # total unpaid break time (mins)

            last_tr = None

            for tr in tours_today:
                if last_tr is not None:
                    # this is not the first tour slot of the day, calculate break time as a pay slot
                    slot_id = '%d_break_%d' % (last_tr.person.id, last_tr.id)
                    desc = 'Break between tours'

                    tour_end = last_ps.time_end
                    pay_end = last_ps.time_start + timedelta(minutes=last_ps.pay_minutes)

                    if pay_end >= tour_end:
                        break_mins = (tr.tour.time_start - pay_end).seconds // 60
                    else:
                        break_mins = (tr.tour.time_start - tour_end).seconds // 60

                    # check if the specific tour paid time overlaps or includes the actual break time (eg. for xmas lights tours)
                    if break_mins > 0:
                        ps_break = RiderPaySlot(
                            source_row_id = slot_id, # important: this should be unique!
                            source = 'generate_pay_report',
                            person = last_tr.person,
                            slot_type = 'break',
                            tour_rider = last_tr,
                            time_start = last_ps.time_end,
                            time_end = tr.tour.time_start,
                            pay_minutes = break_mins,
                        )

                        if break_pay_rate:
                            ps_break.pay_rate = break_pay_rate
                            ps_break.pay_reason = 'Paid breaks rate'
                        else:
                            ps_break.pay_rate = last_ps.pay_rate
                            ps_break.pay_reason = last_ps.pay_reason

                        if paid_break_max:
                            # all breaks under the paid_break_max time are paid, disregard other options
                            if break_mins > paid_break_max:
                                ps_break.pay_rate = 0
                                ps_break.pay_reason = ''
                                ps_break.description = 'Unpaid break'
                            else:
                                ps_break.description = 'Paid break'

                        elif my_total_mins >= time_before_unpaid_break and my_unpaid_break < daily_unpaid_break_mins:
                            # check if the total paid time so far allows an unpaid break, and we have not exceeded max unpaid break time yet
                            unpaid_break_mins = min(daily_unpaid_break_mins - my_unpaid_break, break_mins)
                            daily_unpaid_break_mins += unpaid_break_mins
                            break_paid_mins = break_mins - unpaid_break_mins
                            my_unpaid_break += unpaid_break_mins
                            desc = 'Unpaid break' if break_mins == 0 else 'Partially unpaid break'

                            if break_paid_mins > 0:
                                ps_break.description = 'Partially paid break'
                                ps_break.pay_minutes = break_paid_mins
                            else:
                                ps_break.description = 'Unpaid break'
                                ps_break.pay_rate = 0
                                ps_break.pay_reason = ''

                        my_total_break += break_mins
                        my_total_mins += break_mins

                        pay_slots.append(ps_break)
                        my_pay_slots.append(ps_break)
                
                pay_rate, pay_reason = get_pay_rate(pay_config, tr)

                # configured "paid time" for the tour type should override the actual time duration
                pay_time = (tr.tour.time_end - tr.tour.time_start).seconds // 60
                if (cfg_pay_time := pay_config.get('tour_types', {}).get(tr.tour.tour_type, {}).get('paid_duration_mins', 0)):
                    pay_time = cfg_pay_time

                slot_id = '%d_tour_%d' % (tr.person.id, tr.id)
                
                ps = RiderPaySlot(
                    source_row_id = slot_id,
                    source = 'generate_pay_report',
                    person = tr.person,
                    slot_type = 'tour',
                    tour_rider = tr,
                    pay_rate = pay_rate,
                    pay_reason = pay_reason,
                    pay_minutes = pay_time,
                    description = '%s (Role: %s)' % (tr.tour.tour_type, RIDER_ROLES[tr.rider_role][1]),
                    time_start = tr.tour.time_start,
                    time_end = tr.tour.time_end,
                )

                my_total_mins += pay_time

                pay_slots.append(ps)
                my_pay_slots.append(ps)
                tour_types_seen.add(tr.tour.tour_type)

                last_tr = tr
                last_ps = ps
            
            # do some last things before moving on to the next day
            logger.debug('%s rider %s: %d payslots, %d mins paid, %d paid break, %d unpaid break' %
                (day.isoformat(), last_tr.person.display_name, len(my_pay_slots), my_total_mins, my_total_break, my_unpaid_break))
            
            if my_total_mins < min_daily_mins:
                # update last payslot with difference
                extra_mins = min_daily_mins - my_total_mins
                pay_slots.append(RiderPaySlot(
                    source_row_id = '%d_extra_%d' % (last_tr.person.id, last_tr.id),
                    source = 'generate_pay_report',
                    person = last_tr.person,
                    slot_type = 'break',
                    tour_rider = last_tr,
                    pay_rate = last_ps.pay_rate,
                    pay_reason = last_ps.pay_reason,
                    pay_minutes = extra_mins,
                    description = 'Extra pay (minimum %0.2fh)' % (min_daily_mins / 60),
                    time_start = last_ps.time_end,
                    time_end = last_ps.time_end + timedelta(minutes=extra_mins),
                ))

    return pay_slots, tour_types_seen

def update_payslots(payslot_data):
    """ Updates payslots in database with json-style payslot data """
    payslots = {
        ps.get('id'): ps for ps in payslot_data
    }
    with transaction.atomic():
        payslots_db = RiderPaySlot.objects.in_bulk(id_list=payslots.keys())

        for ps_id, ps_json in payslots.items():
            ps = payslots_db.get(ps_id)
            if ps is None:
                continue

            ps.update_from_dict(ps_json, 'user')
            ps.save()


def update_db_rowset(changed, added, deleted, change_source, existing_rows):
    """
    Typical input comes from match_and_compare_rows().
    Returns resulting list of rows, including deleted rows marked with source_row_state='deleted'.
    """
    result_set = {
        row.id: row for row in existing_rows
    }

    with transaction.atomic():
        # New rows which are matched with an existing row: update the existing row, preserve row ID
        for row_id, chg in changed.items():
            # chg is a 3-tuple of (old_inst, new_inst, diff) - from match_and_compare_rows
            # diff is a dict of field_name: (old_value, new_value)
            # create a Changes row to represent each create/update/delete operation performed on the DB

            existing_row = chg[0]
            # copy the new data into the existing Model instance
            for field_name, diff in chg[2].items():
                existing_row.update_field(field_name, diff[1], change_source)
            existing_row.save()
            result_set[existing_row.id] = existing_row

        # New rows
        for row_id, new_row in added.items():
            new_row.source = change_source
            new_row.save()
            result_set[new_row.id] = new_row

        # Deleted rows
        for row_id, del_row in deleted.items():
            del_row.source_row_state = 'deleted'
            del_row.save()
            if del_row.id in result_set:
                del result_set[del_row.id]
        
    return result_set.values()


def load_tour_pay_report(start_date, end_date, recalculate=True, reset=False):
    """
    Calculates pay slots based on TourRiders in DB and merges with existing RiderPaySlots from DB in memory.
    """

    pay_config = get_tour_pay_config()
    date_filter = get_date_filter(start_date, end_date, 'time_start')

    result_rows = RiderPaySlot.objects.filter(**date_filter)
    if reset:
        result_rows.delete()
        recalculate = True
    
    if recalculate:
        calc_pay_slots, tour_types_seen = generate_tour_pay_slots(start_date, end_date, pay_config)

        with transaction.atomic():
            existing_pay_slots = RiderPaySlot.objects.filter(**date_filter)

            changed, added, deleted, unchanged, ignored = match_and_compare_rows(
                calc_pay_slots, existing_pay_slots, 'source_row_id',
                fields = RiderPaySlot.MUTABLE_FIELDS,
            )

            logger.info('match_and_compare: %d changes, %d added, %d deleted, %d unchanged' % (len(changed), len(added), len(deleted), len(unchanged)))

            result_rows = update_db_rowset(changed, added, deleted, 'generate_pay_report', existing_rows=existing_pay_slots)

    # start and end datetimes are at midnight on the corresponding day, need to add 1 more day to capture entire 7 day duration
    num_days = (end_date - start_date).days + 1
    days = [
        ((day := add_days(start_date, n)).isoformat(), json_datetime(day), day.strftime('%a %d/%m'))
        for n in range(num_days)
    ]
    #print(end_date-start_date, num_days, days)

    days_slot_counts = { day[0]: 0 for day in days }
    rider_data = {}

    for payslot in result_rows:
        r = payslot.person
        rd = rider_data.setdefault(payslot.person.id, {
            'pay_days': {},
            'id': r.id,
            'name': r.name,
            'phone': r.phone,
            'title': r.display_name,
            'pay_rate': r.override_pay_rate,
            'rider_class': r.rider_class_label(),
            'rider_pay': r.pay_rate(),
            'bsb': r.bank_bsb,
            'acct': r.bank_acct,
        })

        today = localdate(payslot.time_start).isoformat()
        day_slots = rd['pay_days'].setdefault(today, [])
        day_slots.append(payslot.to_json())
        days_slot_counts[today] += 1

    return {
        'tour_pay_config': pay_config,
        #'tour_types_seen': list(tour_types_seen),
        'days': [d for d in days if days_slot_counts[d[0]] > 0],
        'riders': rider_data,
        'start_date': json_datetime(start_date),
        'end_date': json_datetime(end_date),
    }

    return data