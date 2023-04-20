from django.core.management.base import BaseCommand, CommandError
import argparse
from sys import stderr
from dateutil.parser import parse
from datetime import date, datetime

from peddleconcept.tours.fringe import update_from_fringe

class Command(BaseCommand):
    help = 'Import the "Seat Listing with Access Requirements" into today\'s tour schedule'

    def add_arguments(self, parser):
        parser.add_argument('start-date')
        parser.add_argument('end-date')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        start_date = date.fromisoformat(options['start-date'])
        end_date = date.fromisoformat(options['end-date'])

        ok, log = update_from_fringe(start_date, end_date, options['dry_run'])
        print(log, file=stderr)
        