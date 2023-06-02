import json, logging
from datetime import timedelta, date

from django.utils import timezone
from django.urls import reverse
from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from peddleconcept.util import (
    start_of_week, add_days, json_datetime, from_json_date, get_iso_date
)
from peddleconcept.pay_reports import (
    save_tour_pay_config, update_payslots, load_tour_pay_report
)
from .base import render_base
from .decorators import require_person_or_user

logger = logging.getLogger(__name__)

@require_person_or_user(admin=True)
def tour_pays_view(request, year_num=None, week_num=None, week_start=None):
    """ HTML view for Weekly Tour Pays """
    now = timezone.now().date()

    if not week_start:
        year = try_parse_int(year_num) or now.year
        week = try_parse_int(week_num) or now.isocalendar()[1]
        week_start = date.fromisocalendar(year, week, 1)
    elif not (week_start := get_iso_date(week_start)):
        return HttpResponseBadRequest("Bad date format in URL (expecting YYYY-MM-DD)")

    week_start = start_of_week(week_start)
    week_end = week_start + timedelta(days=6)

    ctx = {
        'start_date': week_start.strftime("%a %d/%m/%Y"),
        'end_date': week_end.strftime("%a %d/%m/%Y"),
    }

    jsvars = {
        'urls': {
            'tour_report_data': reverse('tour_pays_data'),
        },
        'start_date': json_datetime(week_start),
        'end_date': json_datetime(week_end),
    }

    return render_base(request, 'report_tours', react=True, context=ctx, jsvars=jsvars)

@require_person_or_user(admin=True)
@require_http_methods(['POST'])
def tour_pays_data_view(request):
    """ JSON data view for TourPayReport (Weekly Tour Pays) """
    reqdata = json.loads(request.body)
    
    if 'report_start_date' in reqdata:
        start_date = from_json_date(reqdata['report_start_date'])
        end_date = from_json_date(reqdata['report_end_date'])

        if 'tour_pay_config' in reqdata:
            save_tour_pay_config(reqdata['tour_pay_config'])
    
        if 'payslots' in reqdata:
            logger.info("updating %d payslots" % len(reqdata['payslots']))
            update_payslots(reqdata['payslots'])

        reset = False
        if 'action' in reqdata:
            if reqdata['action'] == 'reset':
                reset = True

        today = date.today()
        if (today - start_date).days >= 14:
            recalculate = False
        else:
            recalculate = True

        data = load_tour_pay_report(start_date, end_date, recalculate=recalculate, reset=reset)
    else:
        data = {}

    return JsonResponse(data)