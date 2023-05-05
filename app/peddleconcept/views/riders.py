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
    RiderSetupBeginForm, RiderSetupProfileForm, get_form_fields,
    PersonProfileForm, PayrollProfileForm,
)
from peddleconcept.email import send_account_auth_email
from .decorators import require_person_or_user, get_rider_setup_redirect, require_null_person

logger = logging.getLogger(__name__)

@require_person_or_user()
def rider_list_view(request):
    """ Rider Contacts page """
    return render(request, 'rider_list.html', {
        'riders': Person.objects.all(),
    })

@require_person_or_user(person=True)
def my_profile_view(request):
    if request.method == 'POST':
        form = PersonProfileForm(request.POST, instance=request.person)
        if form.is_valid():
            form.save()
            messages.success(request, 'Rider details updated')
        else:
            messages.error(request, 'Not saved! Please correct the errors below')
    else:
        form = ProfileForm(instance=request.person)

    return render(request, 'rider_profile.html', {
        'form': get_form_fields(form),
        'form_errors': form.non_field_errors(),
    })

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
            return HttpResponseRedirect(reverse('my_profile'))
    else:
        form = RiderSetupProfileForm(instance=obj)

    return render(request, 'rider_setup_final.html', {'form': get_form_fields(form)})

        