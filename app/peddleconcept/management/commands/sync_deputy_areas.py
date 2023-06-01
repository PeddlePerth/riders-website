from django.core.management.base import BaseCommand, CommandError
import argparse
from sys import stderr
from dateutil.parser import parse
from datetime import date, datetime

from django.db import transaction

from peddleconcept.deputy import sync_deputy_areas

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Download and sync Deputy areas with existing database objects'

    def add_arguments(self, parser):
        pass
    
    @transaction.atomic
    def handle(self, *args, overwrite_existing=False, **options):
        sync_deputy_areas()