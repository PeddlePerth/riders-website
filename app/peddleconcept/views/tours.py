import json

from django.http import HttpResponseRedirect, HttpResponseBadRequest, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from django.urls import reverse

from peddleconcept.models import Person
from peddleconcept.util import (
    json_datetime, get_iso_date, from_json_date
)
from peddleconcept.tours.schedules import (
    get_tour_schedule_data, get_rider_schedule, save_tour_schedule
)

from .base import render_base

@login_required
def schedules_view(request, tours_date=None):
    """ HTML view for Tour Schedule Viewer """
    if not (tours_date := get_iso_date(tours_date)):
        return HttpResponseRedirect(reverse('tours_today'))

    try:
        person = Person.objects.get(user=request.user)
    except (Person.MultipleObjectsReturned, Person.DoesNotExist):
        person = None

    jsvars = {
        'data_url': reverse('tour_sched_data'),
        'update_url': reverse('update_tours'),
        'report_url': reverse('tour_pays', kwargs={'week_start': 'DATE'}),
        'view_url': reverse('tours_for', kwargs={'tours_date': 'DATE'}),
        'today_url': reverse('tours_today'),
        'edit_url': reverse('tour_sched_edit', kwargs={'tours_date': 'DATE'}),
        'venues_report_url': reverse('venues_report', kwargs={'week_start': 'DATE'}),
        'tours_date': json_datetime(tours_date),
        'rider_id': person.id if person else None,
        'is_admin': request.user.is_staff,
    }

    return render_base(request, 'schedules', react=True, jsvars=jsvars)

@login_required
def rider_schedules_view(request, tours_date=None):
    """ HTML view for Rider Tour Schedule """
    if not (tours_date := get_iso_date(tours_date)):
        return HttpResponseRedirect(reverse('tours_rider_today'))

    jsvars = {
        'data_url': reverse('tour_sched_data'),
        'my_url': reverse('tours_rider', kwargs={'tours_date': 'DATE'}),
        'today_url': reverse('tours_rider_today'),
        'view_url': reverse('tours_for', kwargs={'tours_date': 'DATE'}),
        'date': json_datetime(tours_date),
        'rider_id': request.user.id if request.user.is_rider else None,
    }

    return render_base(request, 'schedules_rider', react=True, jsvars=jsvars)


@login_required
@require_http_methods(['POST'])
def tours_data_view(request):
    """ Same data view for Tour Schedule Viewer, Rider Tour Schedule and Tour Schedule Editor """
    reqdata = json.loads(request.body)
    if not 'tours_date' in reqdata:
        return HttpResponseBadRequest()
    tours_date = from_json_date(reqdata['tours_date'])
    
    if 'tours' in reqdata:
        if request.user.is_staff:
            save_tour_schedule(tours_date, reqdata)
        else:
            return HttpResponseBadRequest()

    if 'riderTours' in reqdata:
        data = get_rider_schedule(tours_date, request.user)
    else:
        data = get_tour_schedule_data(tours_date)
    return JsonResponse(data)

