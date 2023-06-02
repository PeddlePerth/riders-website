import json
from datetime import timedelta
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.http import HttpResponseRedirect, HttpResponseBadRequest, JsonResponse, HttpResponse

from peddleconcept.util import (
    get_date_filter, get_iso_date, json_datetime, from_json_date, from_json_date,
    start_of_week
)
from peddleconcept.tours.schedules import (
    get_autoscan_status, get_tour_summary, get_venues_report
)
from peddleconcept.tours.rezdy import update_from_rezdy
from peddleconcept.tours.fringe import update_from_fringe
from peddleconcept.models import Area

from .base import render_base
from .decorators import staff_required
from .tours import get_schedule_or_redirect

@user_passes_test(staff_required)
def schedule_editor_view(request, tour_area_id=None, tours_date=None):
    """ HTML View for Tour Schedule Editor """
    res = get_schedule_or_redirect(tour_area_id, tours_date)
    if isinstance(res, HttpResponse):
        return res
    else:
        tours_date, tour_area = res

    date_filter = get_date_filter(tours_date, tours_date, 'time_start')

    ctx = {
        'date': tours_date,
        'tour_area': tour_area,
    }

    jsvars = {
        'urls': {
            'tour_sched_data': reverse('tour_sched_data'),
            'tours_for': reverse('tours_for', kwargs={'tour_area_id': 'AREA_ID', 'tours_date': 'DATE'}),
        },
        'tour_areas': { area.id: area.to_json() for area in Area.objects.filter(active=True) },
        'admin_url': reverse('admin:peddleconcept_tour_change', args=['TOUR_ID']),
        'tours_date': json_datetime(tours_date),
        'tour_area_id': tour_area.id,
    }
    return render_base(request, 'schedules_editor', react=True, context=ctx, jsvars=jsvars)

@user_passes_test(staff_required)
def schedules_dashboard_view(request, tours_date=None):
    """ HTML view for Tour Dashboard """
    if not get_iso_date(tours_date):
        today = timezone.now().date()
    else:
        today = get_iso_date(tours_date)

    last_scan_begin, last_scan, scan_interval = get_autoscan_status()

    jsvars = {
        'date': json_datetime(today),
        'data_url': reverse('tour_dashboard_data'),
        'tour_areas': { area.id: area.to_json() for area in Area.objects.filter(active=True) },
        'report_url': reverse('tour_pays', kwargs={'week_start': 'DATE'}),
        'view_url': reverse('tours_for', kwargs={'tour_area_id': 'AREA_ID', 'tours_date': 'DATE'}),
        'edit_url': reverse('tour_sched_edit', kwargs={'tour_area_id': 'AREA_ID', 'tours_date': 'DATE'}),
        'update_url': reverse('update_tours'),
        'venues_report_url': reverse('venues_report', kwargs={'week_start': 'DATE'}),
        'last_scan_begin': json_datetime(last_scan_begin),
        'last_scan': json_datetime(last_scan),
        'scan_interval': scan_interval,
    }
    return render_base(request, 'tour_dashboard', jsvars=jsvars, react=True)


@user_passes_test(staff_required)
@require_http_methods(['POST'])
def schedules_dashboard_data_view(request):
    """ JSON Data view for Tour Dashboard """
    try:
        reqdata = json.loads(request.body)
        start_date = from_json_date(reqdata['start_date'])
        end_date = from_json_date(reqdata['end_date'])

    except (KeyError, ValueError, json.JSONDecodeError):
        return HttpResponseBadRequest()

    if not start_date or not end_date:
        return HttpResponseBadRequest()

    data = {
        'tours': get_tour_summary(start_date, end_date),
    }
    return JsonResponse(data)
    

@user_passes_test(staff_required)
@require_http_methods(['POST'])
def update_tours_data(request):
    try:
        reqdata = json.loads(request.body)
        tours_date = from_json_date(reqdata['tours_date'])
        update_rezdy = reqdata['update_rezdy'] == True
        update_fringe = reqdata['update_fringe'] == True
        is_json = True
    except (KeyError, ValueError, json.JSONDecodeError):
        return HttpResponseBadRequest()

    updates = (
        (update_rezdy, update_from_rezdy),
        (update_fringe, update_from_fringe),
    )

    msgs_bad = []

    for flag, update_func in updates:
        if not flag:
            continue

        ok, msg = update_func(tours_date, tours_date)
        if not ok:
            msgs_bad.append(msg)
        
    resp = {
        'tours_date': json_datetime(tours_date),
        'msgs_success': [],
        'msgs_error': msgs_bad,
    }

    return JsonResponse(resp)

@user_passes_test(staff_required)
def venues_report_view(request, week_start=None):
    if not (week_start := get_iso_date(week_start)):
        return HttpResponseBadRequest("Bad date format in URL (expecting YYYY-MM-DD)")

    # correct for days in middle of week
    week_start = start_of_week(week_start)
    week_end = week_start + timedelta(days=6)

    ctx = {
        'start_date': week_start.strftime("%a %d/%m/%Y"),
        'end_date': week_end.strftime("%a %d/%m/%Y"),
    }

    jsvars = {
        'urls': {
            'venues_report_data': reverse('venues_report_data'),
            'dashboard': reverse('tour_dashboard'),
        },
        'start_date': json_datetime(week_start),
        'end_date': json_datetime(week_end),
    }

    return render_base(request, 'report_venues', react=True, context=ctx, jsvars=jsvars)

@user_passes_test(staff_required)
@require_http_methods(['POST'])
def venues_report_data_view(request):
    try:
        reqdata = json.loads(request.body)
        start_date = from_json_date(reqdata['start_date'])
        end_date = from_json_date(reqdata['end_date'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return HttpResponseBadRequest()
    
    if not start_date or not end_date:
        return HttpResponseBadRequest()

    return JsonResponse({
        'venues': get_venues_report(start_date, end_date),
    })
    
