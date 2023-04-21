from functools import wraps
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.urls import reverse

def get_rider_setup_redirect(request):
    if not request.person.active:
        del request.session['person_id']
        messages.error(request, "Your account has been disabled, please contact the administrator")
    elif request.person.signup_status == 'initial':
        messages.info(request, 'Please verify your email address to continue')
        return HttpResponseRedirect(reverse('rider_setup_verify'))
    elif request.person.signup_status == 'confirmed':
        messages.info(request, 'Please enter your details to continue')
        return HttpResponseRedirect(reverse('rider_setup_profile'))
    else:
        # Anything else: redirect to login
        pass
    return HttpResponseRedirect(reverse('accounts:login'))


def staff_required(user):
    return user.is_authenticated and user.is_staff

def require_person_or_user(view_func, user=False, admin=False):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if admin and not request.user.is_authenticated and request.user.is_staff:
            messages.error(request, "You don't have access to that page")
            return HttpResponseRedirect(reverse('home'))

        if user and not request.user.is_authenticated:
            return HttpResponseRedirect(reverse('accounts:login'))

        if not request.user and request.person is not None:
            if not request.person.can_login():
                return get_rider_setup_redirect(request)
        elif not request.user and request.person is None:
            return HttpResponseRedirect(reverse('accounts:login'))

        return view_func(request, *args, **kwargs)
    return wrapper

def require_null_person(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if (request.person and request.person.can_login()) or request.user.is_authenticated:
            messages.info(request, "Already logged in!")
            return HttpResponseRedirect(reverse('home'))
        elif request.person:
            return get_rider_setup_redirect(request)
        
        return view_func(request, *args, **kwargs)
    return wrapper