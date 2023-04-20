import logging

from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms.models import model_to_dict
from django.conf import settings

from peddleconcept.models import Person
from peddleconcept.forms import ProfileForm, get_field

logger = logging.getLogger(__name__)

@login_required
def rider_list_view(request):
    """ Rider Contacts page """
    return render(request, 'rider_list.html', {
        'riders': Person.objects.all(),
    })

@login_required
def homepage_view(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Rider details updated')
        else:
            messages.error(request, 'Missing some details, please correct and try again.')
    else:
        form = ProfileForm(data=model_to_dict(request.user), instance=request.user)
        form.is_valid() # populate errors

    return render(request, 'rider_home.html', {
        'form': { f.name: get_field(f) for f in form },
    })

def token_login_view_deprecated(request, token=None):
    if request.method == 'POST':
        if token is not None or 'userid' not in request.POST or 'token' not in request.POST:
            return HttpResponseBadRequest()
        
        try:
            ptoken = PersonToken.objects.get(
                action = 'login',
                person_id = request.POST['userid'],
                token__exact = request.POST['token'],
            )
        except (PersonToken.DoesNotExist, PersonToken.MultipleObjectsReturned):
            messages.error(request, 'Invalid login token - please contact the administrators')
            logger.error('Failed token login with userid="%s" token="%s"' % (request.POST['userid'], request.POST['token']))
            return HttpResponseRedirect(reverse('login'))
        
        if ptoken.person.user:
            messages.warning(request, 'Please login with your username and password')
            return HttpResponseRedirect(reverse('login'))

        if request.session.get('person_id') == ptoken.person_id:
            messages.success(request, 'Already logged in :)')
        else:
            request.session['person_id'] = ptoken.person_id
            messages.success(request, 'Successfully logged in as %s' % ptoken.person.name)

        return HttpResponseRedirect(reverse('home'))

    else:
        if token is None:
            return HttpResponseRedirect(reverse('login'))
        
        try:
            ptoken = PersonToken.objects.get(
                action = 'login',
                login_token__exact = token
            )
        except (PersonToken.DoesNotExist, PersonToken.MultipleObjectsReturned):
            messages.error(request, 'Invalid login token - please contact the administrators')
            logger.error('Failed token login with token="%s"' % request.POST['token'])
            return HttpResponseRedirect(reverse('login'))
        
        return render(request, 'token_login.html', {
            'newuser': ptoken.person,
            'token': token,
        })
        

def rider_login_view(request, token=None):
    pass