from django.core.management.base import BaseCommand, CommandError
import argparse
from sys import stderr
from dateutil.parser import parse
from datetime import date, datetime

from django.db import transaction

from peddleconcept.util import *
from peddleconcept.models import *

class Command(BaseCommand):
    help = 'Reset field_auto_values for relevant models'

    def add_arguments(self, parser):
        parser.add_argument('--overwrite-existing', action='store_true')

    def handle(self, *args, overwrite_existing=False, **options):
        # changed the code at some point for this to break things, need to adjust the data manually
        models = (Tour, Session, RiderPaySlot, TourRider, TourVenue, Person, Area)
        with transaction.atomic():
            for m in models:
                num_records = 0
                num_empty = 0
                num_fields_changed = 0
                for inst in m.objects.all():
                    if inst.field_auto_values and not overwrite_existing:
                        continue
                    if not inst.field_auto_values:
                        inst.field_auto_values = {}
                        num_empty += 1
                    num_records += 1
                    
                    for f in inst.MUTABLE_FIELDS:
                        val = getattr(inst, f)
                        if not inst.field_auto_values.get(f) or overwrite_existing:
                            if isinstance(val, (datetime, date)):
                                val = json_datetime(val)
                            inst.field_auto_values[f] = val
                            num_fields_changed += 1
                    inst.save()
                print('Model %s: %d records affected, %d empty, %d fields changed' % 
                    (m._meta.model_name, num_records, num_empty, num_fields_changed))
                    

