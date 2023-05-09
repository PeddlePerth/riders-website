import logging
import time

from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth import logout
from django.forms.models import model_to_dict
from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponseBadRequest, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.db.models import Q

from accounts.models import PeddleUser
from peddleconcept.models import Person, PersonToken
from peddleconcept.forms import (
    PersonLoginForm, AuthCodeForm, get_form_fields
)
from peddleconcept.email import send_account_auth_email, validate_auth_token
from .decorators import require_person_or_user, get_rider_setup_redirect, require_null_person
from peddleconcept.middleware import logout_all_session

logger = logging.getLogger(__name__)


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

                request.session['auth_person_id'] = str(obj.id)
                if send_account_auth_email(request, obj.name, obj.email):
                    return HttpResponseRedirect(reverse('rider_login_verify'))
            except (Person.DoesNotExist, Person.MultipleObjectsReturned):
                time.sleep(1) # surely this is bad practice somehow but idk
                logger.warning('Bad rider login attempt with email="%s"' % form.cleaned_data['email'])
                form.add_error('email', 'Please check your email address is correct, or contact an administrator.')
    else:
        form = PersonLoginForm()

    return render(request, 'rider_login.html', {
        'form': get_form_fields(form),
        'form_errors': form.non_field_errors(),
    })

@require_null_person
def rider_login_verify_view(request):
    """ 2nd step of rider login: enter confirmation/auth code """

    person_id = request.session.get('auth_person_id')
    obj = None
    if person_id is not None:
        try:
            obj = Person.objects.get(id=person_id)
        except Person.DoesNotExist:
            pass
    
    if not obj:
        return HttpResponseRedirect(reverse('rider_login'))

    if request.method == 'POST':
        if 'resend' in request.POST:
            send_account_auth_email(request, obj.name, obj.email)
            form = AuthCodeForm()
        else:
            form = AuthCodeForm(data=request.POST)
            if form.is_valid():
                if validate_auth_token(request, form.cleaned_data['auth_code']):
                    obj.last_seen = timezone.now()
                    obj.email_verified = True
                    obj.save()
                    del request.session['auth_person_id']
                    request.session['person_id'] = str(obj.id)
                    return HttpResponseRedirect(reverse('my_profile'))
                else:
                    form.add_error('auth_code', 'Invalid authentication code or code expired. Please try again.')
    else:
        form = AuthCodeForm()
    
    return render(request, 'rider_login_verify.html', {
        'user_email': obj.email,
        'form': get_form_fields(form),
        'form_errors': form.non_field_errors(),
    })


class MyLoginView(auth_views.LoginView):
    def form_valid(self, form):
        """ User auth is valid, check for linked person then login """
        try:
            person = Person.objects.get(user=form.get_user())
            self.request.session['person_id'] = str(person.id)
        except Person.DoesNotExist:
            pass
        except Person.MultipleObjectsReturned:
            messages.warning(self.request, 
                'Multiple Person objects linked to your user account, please fix. '
                'Schedules may not work correctly until you log in again.')
        
        return super().form_valid(form)

class MyLogoutView(auth_views.LogoutView):
    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        """ Logout linked person as well as user """
        logout_all_session(request)
        return super().post(request, *args, **kwargs)