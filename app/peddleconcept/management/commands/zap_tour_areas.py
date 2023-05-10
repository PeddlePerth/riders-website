from django.core.management.base import BaseCommand, CommandError
import argparse
from sys import stderr
from dateutil.parser import parse
from datetime import date, datetime

from django.db import transaction

from peddleconcept.util import *
from peddleconcept.models import *
from peddleconcept.tours.areas import load_areas_locations, get_tour_area, save_areas_locations

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Reload tour areas based on keywords, with option to save and update DB'

    def add_arguments(self, parser):
        parser.add_argument('--update-existing', action='store_true')
        parser.add_argument('--save-areas', action='store_true')

    @transaction.atomic
    def handle(self, *args, overwrite_existing=False, **options):
        update_existing = options['update_existing']
        save_areas = options['save_areas']

        tour_filter = {
            'tour_area__isnull': True
        }
        if update_existing:
            del tour_filter['tour_area__isnull']

        load_areas_locations()

        num_changed = 0
        tours_to_change = list(Tour.objects.filter(**tour_filter))
        for tour in tours_to_change:
            area = get_tour_area(tour.pickup_location)
            if area != tour.tour_area:
                num_changed += 1
                tour.tour_area = area
                tour.save()
        
        logger.info('Updated %d of %d tours with new areas.' % (num_changed, len(tours_to_change)))
        if save_areas:
            save_areas_locations()

                    

