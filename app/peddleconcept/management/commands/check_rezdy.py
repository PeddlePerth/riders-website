from django.core.management.base import BaseCommand, CommandError
import argparse
from sys import stderr
from dateutil.parser import parse
from datetime import date, datetime

from django.db import transaction

from peddleconcept.tours.rezdy import update_from_rezdy
from peddleconcept.util import *
from peddleconcept.models import Tour

class Command(BaseCommand):
    help = 'Import a Rezdy Pickup Manifest (CSV file) to the database'

    def add_arguments(self, parser):
        parser.add_argument('start-date')
        parser.add_argument('end-date')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        start_date = date.fromisoformat(options['start-date'])
        end_date = date.fromisoformat(options['end-date'])
        
        update_from_rezdy(start_date, end_date, dry_run=options['dry_run'])
        