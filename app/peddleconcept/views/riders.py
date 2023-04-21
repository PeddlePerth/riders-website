import logging
import time

from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms.models import model_to_dict
from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponseBadRequest, JsonResponse
from django.urls import reverse
from django.db.models import Q

from accounts.models import PeddleUser
from peddleconcept.models import Person
from peddleconcept.forms import (
    ProfileForm, PersonLoginForm, PersonVerifyCodeForm,
    RiderSetupBeginForm, RiderSetupProfileForm, get_form_fields
)
from peddleconcept.email import send_account_auth_email
from .decorators import require_person_or_user, get_rider_setup_redirect, require_null_person

logger = logging.getLogger(__name__)

@require_person_or_user
def rider_list_view(request):
    """ Rider Contacts page """
    return render(request, 'rider_list.html', {
        'riders': Person.objects.all(),
    })

@require_person_or_user
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

    return render(request, 'rider_home.html', {'form': get_form_fields(form)})

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

        if request.person and request.person.id == ptoken.person_id:
            messages.success(request, 'Already logged in :)')
            return HttpResponseRedirect(reverse('home'))
        
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
                if ptoken.is_valid():
                    del request.session['person_auth_verify']
                    request.session['person_id'] = str(obj.id)
                    return HttpResponseRedirect(reverse('home'))
            except (PersonToken.DoesNotExist, PersonToken.MultipleObjectsReturned):
                messages.error(request, 'Invalid authentication code, please try again')
                return HttpResponseRedirect(reverse('rider_login'))
    else:
        form = PersonVerifyCodeForm()
    
    return render(request, 'rider_login_verify.html', {'form': get_form_fields(form)})

@require_null_person
def rider_setup_begin_view(request):
    """ Rider setup stage 1 of 3: enter name & email """
    if 'person_setup' in request.session: # store ID of person object we are currently working with
        if request.session['person_setup_stage'] == 'verify':
            return HttpResponseRedirect(reverse('rider_setup_verify'))
        elif request.session['person_setup_stage'] == 'final':
            return HttpResponseRedirect(reverse('rider_setup_final'))
        
        try:
            obj = Person.objects.get(id=request.session['person_setup'])
        except Person.DoesNotExist:
            messages.warning(request, "Your previously incomplete account was deleted. Please start again.")
            del request.session['person_setup']
            del request.session['person_setup_stage']
            obj = None
    else:
        obj = None 

    if request.method == 'POST':
        form = RiderSetupBeginForm(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.display_name = fname.title() + ' ' + "".join((n[0].upper() for n in lname.split(' ')))
            obj.last_seen = timezone.now()
            obj.active = False
            obj.email_verified = False
            obj.save()
            request.session['person_setup'] = str(obj.id)
            request.session['person_setup_stage'] = 'initial'

            if send_account_auth_email(obj):
                request.session['person_setup_stage'] = 'verify'
                return HttpResponseRedirect(reverse('rider_setup_verify'))
            else:
                logger.error('Error sending auth email for NEW user: %s' % (str(obj)))
                messages.error('Error sending verification email! Check your details are correct and try again.')
    else:
        form = RiderSetupBeginForm(instance=obj)

    return render(request, 'rider_setup_begin.html', {'form': get_form_fields(form)})

@require_null_person
def rider_setup_verify_view(request):
    """ Rider setup Part 2 of 3: verify email by entering auth code """
    person_id = request.session.get('person_setup')
    setup_stage = request.session.get('person_setup_stage')
    if person_id is None or setup_stage == 'initial':
        return HttpResponseRedirect(reverse('rider_setup_begin'))
    elif setup_stage == 'final':
        return HttpResponseRedirect(reverse('rider_setup_final'))

    try:
        obj = Person.objects.get(id=person_id)
    except Person.DoesNotExist:
        # go back to start
        request.session['person_setup_stage'] = 'initial'
        return HttpResponseRedirect(reverse('rider_setup_begin'))

    if request.method == 'POST':
        form = PersonVerifyCodeForm(request.POST)
        if form.is_valid():
            try:
                ptoken = PersonToken.objects.get(
                    person = obj,
                    action = 'auth_email',
                    token = form.cleaned_data['auth_code'],
                )
                if ptoken.is_valid():
                    obj.email_verified = True
                    obj.signup_status = 'confirmed'
                    obj.save()
                    ptoken.delete()
                    request.session['person_setup_stage'] = 'final'
                    return HttpResponseRedirect(reverse('rider_setup_final'))
                else:
                    messages.error(request, 'Authentication code has expired, please start again')
                    request.session['person_setup_stage'] = 'initial'
                    return HttpResponseRedirect(reverse('rider_setup_initial'))
            except (PersonToken.DoesNotExist, PersonToken.MultipleObjectsReturned):
                # Start over for failed auth code - user can re-enter details if they didn't get the code right
                messages.error(request, 'Invalid authentication code, please start again')
                request.session['person_setup_stage'] = 'initial'
                return HttpResponseRedirect(reverse('rider_setup_initial'))
    else:
        form = PersonVerifyCodeForm()

    return render(request, 'rider_setup_verify.html', {'form': get_form_fields(form)})

@require_null_person
def rider_setup_final_view(request):
    """ Rider setup part 3 of 3: enter profile & payment details """
    person_id = request.session.get('person_setup')
    setup_stage = request.session.get('person_setup_stage')
    if person_id is None or setup_stage == 'initial':
        return HttpResponseRedirect(reverse('rider_setup_begin'))
    elif setup_stage == 'verify':
        return HttpResponseRedirect(reverse('rider_setup_verify'))

    try:
        obj = Person.objects.get(id=person_id)
    except Person.DoesNotExist:
        # go back to start
        request.session['person_setup_stage'] = 'initial'
        return HttpResponseRedirect(reverse('rider_setup_begin'))

    if request.method == 'POST':
        form = RiderSetupProfileForm(data=request.POST, instance=obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.active = True
            obj.signup_status = 'complete'
            if not obj.rider_class:
                obj.rider_class = 'rider_probationary'
            obj.last_seen = timezone.now()
            obj.save()

            del request.session['person_setup']
            del request.session['person_setup_stage']
            request.session['person_id'] = str(obj.id)
            return HttpResponseRedirect(reverse('home'))
    else:
        form = RiderSetupProfileForm(instance=obj)

    return render(request, 'rider_setup_final.html', {'form': get_form_fields(form)})

        