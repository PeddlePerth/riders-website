from django.core.management.base import BaseCommand, CommandError
import argparse
from sys import stderr
from datetime import date, datetime
from peddleconcept.util import json_datetime, from_json_datetime, add_days

from django.db import transaction

from peddleconcept.models import Settings
from peddleconcept.settings import get_setting_or_default, set_setting, get_auto_update_setting, AUTO_UPDATE_STATUS, AUTO_UPDATE_SETTING
from peddleconcept.tours.rezdy import update_from_rezdy
from peddleconcept.tours.fringe import update_from_fringe

class Command(BaseCommand):
    help = 'Tweak some data in the database'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help="Show what would be run without doing anything")
        parser.add_argument('--force', action='store_true', help='Run a scan regardless of the last scan time')
        parser.add_argument('--start-date', help='Date from which to start scanning, defaults to today (iso format)')
        parser.add_argument('--num-days', help='Override number of days in settings', type=int)

    def handle(self, *args, dry_run=False, force=False, start_date=None, num_days=None, **kwargs):
        scan_status = get_setting_or_default(AUTO_UPDATE_STATUS, {
            'last_update_begin': 0,
            'last_update': 0,
            'last_dispatch': json_datetime(datetime.now()),
            'last_update_status': None,
        })

        scan_config = get_auto_update_setting()

        try:
            update_fringe = scan_config['auto_update_fringe']
            update_rezdy = scan_config['auto_update_rezdy']
            scan_days_before = int(scan_config['scan_days_behind'])
            scan_days_ahead = int(scan_config['scan_days_ahead'])
            auto_update_interval = int(scan_config['update_interval_minutes'])
        except (KeyError, TypeError):
            raise CommandError("Invalid syntax in configuration setting '%s'" % AUTO_UPDATE_SETTING)

        now = datetime.now()
        last_update = from_json_datetime(scan_status.get('last_update', 0))
        last_update_mins = (now - last_update).total_seconds() // 60
        last_dispatch = from_json_datetime(scan_status.get('last_dispatch', 0))
        print('Last update at %s (%d minutes ago), last dispatch at %s' % (last_update, last_update_mins, last_dispatch), file=stderr)

        if start_date:
            force = True
            start_date = date.fromisoformat(start_date)
            if not num_days:
                num_days = scan_days_ahead
        else:
            start_date = add_days(now.date(), -scan_days_before)
            scan_status['last_dispatch'] = json_datetime(now)
            scan_status['last_update_begin'] = json_datetime(now)

        if not dry_run:
            set_setting(AUTO_UPDATE_STATUS, scan_status)

        if not force and last_update_mins < auto_update_interval:
            return

        # auto update interval elapsed, time to run it again
        print('Update interval elapsed, performing next scan...', file=stderr)

        if dry_run:
            print('Dry run: not performing DB updates', file=stderr)

        if not num_days:
            num_days = scan_days_before + scan_days_ahead
        end_date = add_days(start_date, num_days)

        start_time = datetime.now()
        status_msgs = []
        rezdy_msg = 'N/A'
        fringe_msg = 'N/A'

        if update_rezdy:
            ok, log = update_from_rezdy(start_date, end_date, dry_run=dry_run)
            print(log, file=stderr)
            status_msgs += log.split('\n')
        if update_fringe:
            ok, log = update_from_fringe(start_date, end_date, dry_run=dry_run)
            print(log, file=stderr)
            status_msgs += log.split('\n')

        end_time = datetime.now()

        print('Autoscan complete for %d days (%s to %s) in %.1f seconds' % (
            num_days, start_date.isoformat(), end_date.isoformat(), (end_time - start_time).total_seconds()), file=stderr)

        if not dry_run:
            if not force:
                scan_status['last_update'] = json_datetime(datetime.now())
            scan_status['last_update_status'] = status_msgs
            set_setting(AUTO_UPDATE_STATUS, scan_status)
            

        

