from functools import wraps
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.urls import reverse
from peddleconcept.middleware import logout_all_session

def get_rider_setup_redirect(request):
    if not request.person.active:
        logout_all_session(request)
        messages.error(request, "Your account has been disabled, please contact the administrator")
    elif request.person.signup_status == 'confirmed':
        messages.info(request, 'Your account is not fully set up. Please complete your profile to continue.')
        return HttpResponseRedirect(reverse('rider_setup_final'))
    elif request.person.signup_status == 'migrated':
        messages.info(request, 'Please confirm your details to continue.')
        return HttpResponseRedirect(reverse('rider_migrate_begin'))
    else:
        # Anything else: redirect to login
        pass
    return HttpResponseRedirect(reverse('login'))

def staff_required(user):
    return user.is_authenticated and user.is_staff

def require_person_or_user(person=False, user=False, admin=False):
    """ Decorator function for views which require a Person (request.person), User or Admin """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if admin and not request.user.is_authenticated and request.user.is_staff:
                messages.error(request, "You don't have access to that page")
                return HttpResponseRedirect(reverse('my_profile'))

            if user and not request.user.is_authenticated:
                return HttpResponseRedirect(reverse('login'))

            if not request.user.is_authenticated and request.person.exists:
                if not request.person.can_login():
                    return get_rider_setup_redirect(request)
            elif not request.user.is_authenticated and not request.person.exists:
                return HttpResponseRedirect(reverse('login'))

            if person and not request.person.exists:
                messages.error(request, 'You do not have a profile associated with this account. Ask an admin to add a Person for you.')
                return HttpResponseRedirect(reverse('index'))

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def require_null_person(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if (request.person.exists and request.person.can_login()) or request.user.is_authenticated:
            messages.info(request, "Already logged in!")
            return HttpResponseRedirect(reverse('my_profile'))
        elif request.person.exists:
            return get_rider_setup_redirect(request)
        
        return view_func(request, *args, **kwargs)
    return wrapper