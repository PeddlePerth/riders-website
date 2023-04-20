from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render
from django.utils.safestring import mark_safe
from django.conf import settings
from django.contrib.auth.decorators import login_required

import json

@login_required
def index_view(request):
    if request.user.is_staff:
        return HttpResponseRedirect(reverse('tour_dashboard'))
    else:
        return HttpResponseRedirect(reverse('tours_today'))

def render_base(request, page_name, react=False, context=None, jsvars={}, template=None):
    ctx = {
        'DEBUG': settings.DEBUG,
        'page_name': page_name,
        'react': react,
        'jsvars': mark_safe(json.dumps(jsvars).replace("'", "\'")),
    }
    if context:
        ctx.update(context)

    return render(request, ('%s.html' % page_name) if template is None else template, context=ctx)

