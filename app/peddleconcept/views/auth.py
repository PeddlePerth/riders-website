import logging
import time

from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.forms.models import model_to_dict
from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponseBadRequest, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.db.models import Q

from accounts.models import PeddleUser
from peddleconcept.models import Person, PersonToken
from peddleconcept.forms import (
    ProfileForm, PersonLoginForm, PersonVerifyCodeForm,
    RiderSetupBeginForm, RiderSetupProfileForm, get_form_fields
)
from peddleconcept.email import send_account_auth_email
from .decorators import require_person_or_user, get_rider_setup_redirect, require_null_person

logger = logging.getLogger(__name__)

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

        if request.person and person.id == ptoken.person_id:
            messages.success(request, 'Already logged in :)')
        else:
            request.session['person_id'] = str(ptoken.person_id)
            messages.success(request, 'Successfully logged in as %s' % ptoken.person.name)
            logger.info('Person login OK: id=%s name="%s" from="%s"' % (
                ptoken.person_id, ptoken.person.name, request.META.get('REMOTE_ADDR')))

        return HttpResponseRedirect(reverse('my_profile'))

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

        if request.person and request.person.id == ptoken.person_id:
            messages.success(request, 'Already logged in :)')
            return HttpResponseRedirect(reverse('my_profile'))
        
        return render(request, 'token_login.html', {
            'newuser': ptoken.person,
            'token': token,
        })

@require_null_person 
def rider_login_view(request):
    """ 1st step of 2 step rider login: enter email address, submit, then enter email confirmation/auth code """

    if request.method == 'POST':
        form = PersonLoginForm(data=request.POST)
        if form.is_valid():
            try:
                obj = Person.objects.get(email=form.cleaned_data['email'])
                if obj.user and obj.user.has_usable_password():
                    messages.error(request, 'Please login with your username and password instead')
                    return HttpResponseRedirect(reverse('login'))
                if send_account_auth_email(obj): 
                    request.session['person_auth_verify'] = str(obj.id)
                    return HttpResponseRedirect(reverse('rider_login_verify'))
                else:
                    messages.error(request, 'Error sending login code, please contact an administrator and try again')
            except (Person.DoesNotExist, Person.MultipleObjectsReturned):
                time.sleep(1) # surely this is bad practice somehow but idk
                logger.warning('Bad rider login attempt with email="%s"' % form.cleaned_data['email'])
                messages.error(request, 'Please check your email address is correct, or contact an administrator')
    else:
        form = PersonLoginForm()

    return render(request, 'rider_login.html', {'form': get_form_fields(form)})

@require_null_person
def rider_login_verify_view(request):
    """ 2nd step of rider login: enter confirmation/auth code """

    person_id = request.session.get('person_auth_verify')
    obj = None
    if person_id is not None:
        try:
            obj = Person.objects.get(id=person_id)
        except Person.DoesNotExist:
            pass
    
    if not obj:
        return HttpResponseRedirect(reverse('rider_login'))

    if request.method == 'POST':
        form = PersonVerifyCodeForm(data=request.POST)
        if form.is_valid():
            try:
                ptoken = PersonToken.objects.get(
                    person = obj,
                    action = 'auth_email',
                    token = form.cleaned_data['auth_code']
                )

            except (PersonToken.DoesNotExist, PersonToken.MultipleObjectsReturned):
                ptoken = None

            if ptoken is not None and ptoken.is_valid():
                del request.session['person_auth_verify']
                request.session['person_id'] = str(obj.id)
                return HttpResponseRedirect(reverse('my_profile'))
            else:
                messages.error(request, 'Invalid authentication code, please try again')
                return HttpResponseRedirect(reverse('rider_login'))
    else:
        form = PersonVerifyCodeForm()
    
    return render(request, 'rider_login_verify.html', {'form': get_form_fields(form)})


class MyLoginView(auth_views.LoginView):
    def form_valid(self, form):
        """ User auth is valid, check for linked person then login """
        try:
            person = Person.objects.get(user=form.get_user())
            request.session['person_id'] = str(person.user_id)
        except Person.DoesNotExist:
            pass
        except Person.MultipleObjectsReturned:
            messages.warning(self.request, 'Multiple Person objects linked to your user account, please fix. Schedules may not work correctly until you log in again.')

class MyLogoutView(auth_views.LogoutView):
    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        """ Logout linked person as well as user """
        if request.person is not None:
            del request.session['person_id']
        
        return super().post(request, *args, **kwargs)