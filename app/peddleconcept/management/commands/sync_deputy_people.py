from django.core.management.base import BaseCommand, CommandError
import argparse
from sys import stderr
from dateutil.parser import parse
from datetime import date, datetime

from django.db import transaction

from peddleconcept.deputy import sync_deputy_people

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = ''

    def add_arguments(self, parser):
        parser.add_argument('-n', '--dry-run', action='store_true', help='Store no changes in the database')
        parser.add_argument('--match-only', action='store_true', help='Match rows with source_row_id but do not update any data')
        parser.add_argument('--allow-add', action='store_true', help="Add missing Person objects")
        parser.add_argument('--company-id', help='Specify Deputy Company/Location ID')
        parser.add_argument('--disable-riders', action='store_true', help='Disable riders who are not in Deputy')
    
    @transaction.atomic
    def handle(self, *args, overwrite_existing=False, **options):
        company = None
        if options['company_id']:
            company = int(options['company_id'])
        sync_deputy_people(
            dry_run=options['dry_run'], 
            no_add=not options['allow_add'], 
            match_only=options['match_only'],
            company_id=company,
            disable_riders=options['disable_riders'])