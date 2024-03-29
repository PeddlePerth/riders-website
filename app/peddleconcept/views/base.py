from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render
from django.utils.safestring import mark_safe
from django.conf import settings
from .decorators import require_person_or_user

import json
from peddleconcept.models import Area

@require_person_or_user()
def index_view(request):
    if request.user.is_staff:
        return HttpResponseRedirect(reverse('tour_dashboard'))
    else:
        return HttpResponseRedirect(reverse('tours_today'))

def base_context(page_name, react, extra_context, jsvars):
    ctx = {
        'DEBUG': settings.DEBUG,
        'page_name': page_name,
        'react': react,
        'jsvars': mark_safe(json.dumps(jsvars).replace("'", "\'")),
        'tour_areas': Area.objects.filter(active=True).order_by('sort_order'),
    }
    if extra_context:
        ctx.update(extra_context)
    return ctx

def render_base(request, page_name, react=False, context=None, jsvars={}, template=None):
    ctx = base_context(page_name, react, context, jsvars)
    return render(request, ('%s.html' % page_name) if template is None else template, context=ctx)
