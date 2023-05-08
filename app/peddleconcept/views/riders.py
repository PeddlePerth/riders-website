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
from django.utils import timezone

from accounts.models import PeddleUser
from peddleconcept.models import Person, PersonToken
from peddleconcept.forms import (
    EmailConfirmForm, AuthCodeForm,
    RiderSetupBeginForm, RiderSetupProfileForm, get_form_fields,
    PersonProfileForm, PayrollProfileForm,
)
from peddleconcept.email import send_account_auth_email, validate_auth_token, send_payroll_change_email
from .decorators import require_person_or_user, get_rider_setup_redirect, require_null_person

logger = logging.getLogger(__name__)

@require_person_or_user()
def rider_list_view(request):
    """ Rider Contacts page """
    return render(request, 'rider_list.html', {
        'riders': Person.objects.all(),
    })

@require_person_or_user(person=True)
def rider_profile_view(request):
    return render(request, 'rider_profile.html')

@require_person_or_user(person=True)
def rider_profile_edit_view(request):
    if request.method == 'POST':
        form = PersonProfileForm(request.POST, instance=request.person)
        if form.is_valid():
            if form.cleaned_data['email'].lower() != request.person.email.lower():
                if send_account_auth_email(request, request.person.name, form.cleaned_data['email']):
                    request.session['rider_email'] = form.cleaned_data['email']
                    form.save()
                    messages.info(request, 'Rider details updated')
                    return HttpResponseRedirect(reverse('rider_profile_verify_email'))
            else:
                form.save()
                messages.success(request, 'Rider details updated')
                return HttpResponseRedirect(reverse('my_profile'))
    else:
        form = PersonProfileForm(instance=request.person, initial={'email': request.person.email})

    return render(request, 'rider_profile_edit.html', {
        'form': get_form_fields(form),
        'form_errors': form.non_field_errors(),
    })

@require_person_or_user(person=True)
def rider_profile_verify_email_view(request):
    if not 'rider_email' in request.session:
        return HttpResponseRedirect(reverse('my_profile'))
    
    obj = request.person
    if request.method == 'POST':
        if 'resend' in request.POST:
            send_account_auth_email(request, obj.name, request.session['rider_email'])
            form = AuthCodeForm()
        else:
            form = AuthCodeForm(data=request.POST)
            if form.is_valid():
                if validate_auth_token(request, form.cleaned_data['auth_code']):
                    # create the new Person object and populate with data stored in session
                    obj.email = request.session.pop('rider_email')
                    obj.last_seen = timezone.now()
                    obj.email_verified = True
                    obj.save()

                    messages.success(request, 'Your email address has been updated')

                    return HttpResponseRedirect(reverse('my_profile'))
                else:
                    form.add_error('auth_code', 'Invalid authentication code or code expired. Please try again.')
    else:
        form = AuthCodeForm()

    return render(request, 'rider_profile_verify_email.html', {
        'email_old': obj.email,
        'email_new': request.session['rider_email'],
        'form_errors': form.non_field_errors(),
        'form': get_form_fields(form),
    })

@require_person_or_user(person=True)
def rider_profile_edit_payroll_view(request):
    if request.method == 'POST':
        form = PayrollProfileForm(request.POST, instance=request.person)
        if form.is_valid():
            if request.person.email_verified and send_payroll_change_email(request.person):
                form.save()
                messages.success(request, 'Payroll details updated')
                return HttpResponseRedirect(reverse('my_profile'))
            else:
                form.add_error(None, 'There was an error trying to update your payroll details. Make sure your email address is up to date!')
    else:
        form = PayrollProfileForm(instance=request.person)
        
    return render(request, 'rider_profile_edit_payroll.html', {
        'form': get_form_fields(form),
        'form_errors': form.non_field_errors(),
    })

@require_null_person
def rider_token_login_migrate_view(request, token=None):
    """ Riders accessing the website using an old URL are sent to enter/confirm and verify their email """
    try:
        ptoken = PersonToken.objects.get(
            action = 'rider_login_migrated',
            token__exact = token
        )
    except (PersonToken.DoesNotExist, PersonToken.MultipleObjectsReturned):
        pass
    
    if ptoken is None or not ptoken.is_valid():
        logger.error('Failed token login with token="%s"' % request.POST['token'])
        messages.error(request, 'Please login using your email address instead.')
        return HttpResponseRedirect(reverse('rider_login'))
    elif not ptoken.person.can_login():
        logger.error('Token login failed: account incomplete or disabled')
        request.person = ptoken.person
        return get_rider_setup_redirect(request)
    
    request.session['person_id'] = str(ptoken.person.id)
    messages.success(request, 'Now logged in as %s' % ptoken.person.name)
    return HttpResponseRedirect(reverse('rider_migrate_begin'))

@require_person_or_user(person=True)
def rider_migrate_begin_view(request):
    """ Require user to enter/confirm and verify email address before continuing """
    if request.person.signup_status != 'migrated':
        messages.success('Please edit your profile using the My Profile page.')
        return HttpResponseRedirect(reverse('my_profile'))

    if request.method == 'POST':
        form = RiderSetupBeginForm(request.POST, instance=request.person)
        if form.is_valid():
            # don't save the ModelForm - store values in session, same as rider_setup_begin_view
            for x in ('first_name', 'last_name', 'email'):
                request.session['rider_%s' % x] = form.cleaned_data[x]

            # redirect to verify email
            if send_account_auth_email(request, form.cleaned_data['first_name'], form.cleaned_data['email']):
                request.session['rider_migrate_state'] = 'verify'
                return HttpResponseRedirect(reverse('rider_migrate_verify'))
            else:
                logger.error('Error sending auth email for MIGRATED user: %s' % (str(obj)))
    else:
        form = RiderSetupBeginForm(instance=request.person)

    return render(request, 'rider_migrate_begin.html', {
        'form': get_form_fields(form),
        'form_errors': form.non_field_errors(),
    })

@require_person_or_user(person=True)
def rider_migrate_verify_view(request):
    """
    Migration step 2 of 2: Verify the rider's email and update the Person data.
    """
    if request.person.signup_status != 'migrated':
        messages.success(request, 'Please edit your profile using the My Profile page.')
        return HttpResponseRedirect(reverse('my_profile'))
    elif not request.session.get('rider_migrate_state') == 'verify':
        return HttpResponseRedirect(reverse('rider_migrate_begin'))

    obj = request.person
    if request.method == 'POST':
        if 'resend' in request.POST:
            send_account_auth_email(request, obj.name, obj.email)
            form = AuthCodeForm()
        else:
            form = AuthCodeForm(data=request.POST)
            if form.is_valid():
                if validate_auth_token(request, form.cleaned_data['auth_code']):
                    # create the new Person object and populate with data stored in session
                    obj.fname = request.session.pop('rider_first_name')
                    obj.lname = request.session.pop('rider_last_name')
                    obj.email = request.session.pop('rider_email')
                    obj.last_seen = timezone.now()
                    obj.email_verified = True
                    obj.signup_status = 'complete'
                    obj.save()

                    del request.session['rider_migrate_state']
                    request.session['person_id'] = str(obj.id)
                    num_del, num_types = PersonToken.objects.filter(person=obj, action='rider_login_migrated').delete()
                    logger.info("Migrated rider verification completed for user %s <%s> (deleted %d PersonTokens)" % (
                        obj.name, obj.email, num_del
                    ))
                    messages.success(request, 'Thanks for verifying your account!')

                    return HttpResponseRedirect(reverse('my_profile'))
                else:
                    form.add_error('auth_code', 'Invalid authentication code or code expired. Please try again.')
    else:
        form = AuthCodeForm()

    return render(request, 'rider_setup_verify.html', {
        'form_errors': form.non_field_errors(),
        'form': get_form_fields(form),
    })

@require_null_person
def rider_setup_invite_view(request, token=None):
    """ Signup invitation URL: eg. for use in Google Classroom """
    try:
        ptoken = PersonToken.objects.get(
            action = 'rider_invite_generic',
            token__exact = token,
        )
    except (PersonToken.DoesNotExist, PersonToken.MultipleObjectsReturned):
        ptoken = None

    if not ptoken or not ptoken.is_valid():
        return HttpResponseBadRequest('Invalid invitation URL - please contact the administrators.')

    # begin rider setup session
    request.session['rider_setup_state'] = 'invited'
    logger.info('Rider setup invitation token activated')
    return HttpResponseRedirect(reverse('rider_setup_begin'))

@require_null_person
def rider_setup_begin_view(request):
    """ Rider setup stage 1 of 3: enter name & email """
    if (state := request.session.get('rider_setup_state')) is None:
        # not allowed unless invited somehow
        return HttpResponseRedirect(reverse('login'))

    # check if we are in a diferent part of the procedure, and redirect accordingly
    if state == 'verify':
        messages.warning('Redirected')
        return HttpResponseRedirect(reverse('rider_setup_verify'))
    elif state == 'final':
        messages.warning('Redirected')
        return HttpResponseRedirect(reverse('rider_setup_final'))
    
    if request.method == 'POST':
        form = RiderSetupBeginForm(request.POST)
        if form.is_valid():
            # don't save the ModelForm - store values in session, same as rider_migrate_begin_view
            for x in ('first_name', 'last_name', 'email'):
                request.session['rider_%s' % x] = form.cleaned_data[x]

            if send_account_auth_email(request, form.cleaned_data['first_name'], form.cleaned_data['email']):
                request.session['rider_setup_state'] = 'verify'
                return HttpResponseRedirect(reverse('rider_setup_verify'))
            else:
                logger.error('Error sending auth email for NEW user: %s' % (str(form.cleaned_data)))
    else:
        form = RiderSetupBeginForm()

    return render(request, 'rider_setup_begin.html', {
        'form': get_form_fields(form),
        'form_errors': form.non_field_errors(),
    })

@require_null_person
def rider_setup_verify_view(request):
    """
    New rider setup Part 2 of 3: verify email by entering auth code, then continue to payroll form.
    Migrated rider setup part 2 of 2: verify email then continue to website.
    """
    state = request.session.get('rider_setup_state')
    if state == 'invited':
        return HttpResponseRedirect(reverse('rider_setup_begin'))
    elif state == 'final':
        return HttpResponseRedirect(reverse('rider_setup_final'))

    if request.method == 'POST':
        if 'resend' in request.POST:
            send_account_auth_email(request, request.session['rider_first_name'], request.session['rider_email'])
            form = AuthCodeForm()
        else:
            form = AuthCodeForm(data=request.POST)
            if form.is_valid():
                if validate_auth_token(request, form.cleaned_data['auth_code']):
                    # create the new Person object and populate with data stored in session
                    fname = request.session.pop('rider_first_name')
                    lname = request.session.pop('rider_last_name')
                    obj = Person(
                        first_name = fname,
                        last_name = lname,
                        display_name = fname.title() + ' ' + "".join((n[0].upper() for n in lname.split(' ') if len(n) > 0)),
                        email = request.session.pop('rider_email'),
                        email_verified = True,
                        active = False,
                        signup_status = 'confirmed',
                        rider_class = 'rider_probationary',
                        last_seen = timezone.now(),
                    )
                    obj.save()

                    request.session['rider_setup_state'] = 'final'
                    request.session['person_id'] = str(obj.id)
                    return HttpResponseRedirect(reverse('rider_setup_final'))
                else:
                    form.add_error('auth_code', 'Invalid authentication code or code expired. Please try again.')
    else:
        form = AuthCodeForm()

    return render(request, 'rider_setup_verify.html', {
        'user_email': request.session.get('rider_email'),
        'form_errors': form.non_field_errors(),
        'form': get_form_fields(form)}
    )

def rider_setup_final_view(request):
    """ Rider setup part 3 of 3: enter profile & payment details """
    state = request.session.get('rider_setup_state')
    if state == 'invited':
        return HttpResponseRedirect(reverse('rider_setup_begin'))
    elif state == 'verify':
        return HttpResponseRedirect(reverse('rider_setup_verify'))
    elif request.person.can_login():
        messages.info(request, 'Your account is already activated! Please edit your profile here instead.')
        return HttpResponseRedirect(reverse('my_profile'))
    elif state != 'final' or not request.person.exists:
        return HttpResponseRedirect(reverse('login'))
    
    if request.method == 'POST':
        form = RiderSetupProfileForm(data=request.POST, instance=request.person)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.active = True
            obj.signup_status = 'complete'
            obj.last_seen = timezone.now()
            obj.save()

            del request.session['rider_setup_state']
            request.session['person_id'] = str(obj.id)
            return HttpResponseRedirect(reverse('my_profile'))
    else:
        form = RiderSetupProfileForm(instance=request.person)

    return render(request, 'rider_setup_final.html', {
        'form_errors': form.non_field_errors(),
        'form': get_form_fields(form)
    })
