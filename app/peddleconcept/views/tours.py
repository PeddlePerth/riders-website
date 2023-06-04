import json

from django.http import HttpResponseRedirect, HttpResponseBadRequest, JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from django.urls import reverse

from peddleconcept.models import Person, Area
from peddleconcept.util import (
    json_datetime, get_iso_date, from_json_date, today
)
from peddleconcept.tours.schedules import (
    get_tour_schedule_data, get_rider_schedule, save_tour_schedule
)

from .base import render_base
from .decorators import require_person_or_user

def get_schedule_or_redirect(tour_area_id, tours_date):
    """ returns: (redirect:bool, tour_area:Area, tours_date:date) """
    redirect = False
    try:
        area = Area.objects.get(pk=tour_area_id, active=True)
    except (Area.DoesNotExist, ValueError):
        redirect = True
        # default tour area
        area = Area.objects.filter(active=True).order_by('sort_order').first()

    if not (tours_date := get_iso_date(tours_date)):
        redirect = True
    
    if redirect:
        if not tours_date or tours_date == today():
            url = reverse('tours_today', kwargs={'tour_area_id': area.id})
        else:
            url = reverse('tours_for', kwargs={'tour_area_id': area.id, 'tours_date': tours_date.isoformat()})
        return HttpResponseRedirect(url)

    return tours_date, area

@require_person_or_user()
def schedules_view(request, tours_date=None, tour_area_id=None):
    """ HTML view for Tour Schedule Viewer """

    res = get_schedule_or_redirect(tour_area_id, tours_date)
    if isinstance(res, HttpResponse):
        return res
    else:
        tours_date, tour_area = res

    jsvars = {
        'data_url': reverse('tour_sched_data'),
        'update_url': reverse('update_tours'),
        'tour_area_id': tour_area.id,
        'tour_areas': { area.id: area.to_json() for area in Area.objects.filter(active=True) },
        'report_url': reverse('tour_pays', kwargs={'week_start': 'DATE'}),
        'view_url': reverse('tours_for', kwargs={'tour_area_id': 'AREA_ID', 'tours_date': 'DATE'}),
        'today_url': reverse('tours_today', kwargs={'tour_area_id': 'AREA_ID'}),
        'edit_url': reverse('tour_sched_edit', kwargs={'tour_area_id': 'AREA_ID', 'tours_date': 'DATE'}),
        'venues_report_url': reverse('venues_report', kwargs={'week_start': 'DATE'}),
        'tours_date': json_datetime(tours_date),
        'rider_id': request.person.id if request.person.exists else None,
        'is_admin': request.user.is_staff,
    }

    return render_base(request, 'schedules', react=True, jsvars=jsvars)

@require_person_or_user(person=True)
def rider_schedules_view(request, tours_date=None):
    """ HTML view for Rider Tour Schedule """
    if not (tours_date := get_iso_date(tours_date)):
        return HttpResponseRedirect(reverse('tours_rider_today'))

    jsvars = {
        'data_url': reverse('tours_rider_data'),
        'my_url': reverse('tours_rider', kwargs={'tours_date': 'DATE'}),
        'today_url': reverse('tours_rider_today'),
        'view_url': reverse('tours_for', kwargs={'tour_area_id': 'AREA_ID', 'tours_date': 'DATE'}),
        'date': json_datetime(tours_date), # whichever date is in the URL = currently selected date
        'rider_id': request.person.id,
    }

    return render_base(request, 'schedules_rider', react=True, jsvars=jsvars)

@require_person_or_user(person=True)
def rider_tours_data_view(request):
    reqdata = json.loads(request.body)
    if not 'startDate' in reqdata or not 'endDate' in reqdata:
        return HttpResponseBadRequest('Missing rider tour startDate or endDate')
    
    start_date = from_json_date(reqdata['startDate'])
    end_date = from_json_date(reqdata['endDate'])

    return JsonResponse(get_rider_schedule(start_date, end_date, request.person))

@require_person_or_user()
@require_http_methods(['POST'])
def tours_data_view(request):
    """ Same data view for Tour Schedule Viewer, Rider Tour Schedule and Tour Schedule Editor """
    reqdata = json.loads(request.body)
    if not 'tours_date' in reqdata or not 'tour_area_id' in reqdata:
        return HttpResponseBadRequest('Missing tour_area_id or tours_date')
    tours_date = from_json_date(reqdata['tours_date'])

    try:
        tour_area = Area.objects.get(active=True, id=reqdata['tour_area_id'])
    except (ValueError, Area.DoesNotExist):
        return HttpResponseBadRequest('Invalid tour_area_id')
    
    if 'tours' in reqdata:
        if request.user.is_staff:
            save_tour_schedule(tours_date, reqdata)
        else:
            return HttpResponseBadRequest()

    in_editor = reqdata.get('in_editor', False) and request.user.is_staff

    data = get_tour_schedule_data(tour_area, tours_date, in_editor=in_editor)
    return JsonResponse(data)

