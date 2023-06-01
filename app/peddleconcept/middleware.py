from django.utils.functional import SimpleLazyObject
from django.contrib.auth import logout
from peddleconcept.models import Person
from django.conf import settings

SESSION_MIN_AGE = getattr(settings, 'SESSION_COOKIE_AGE', 3600*24*14) // 2

def logout_all_session(request):
    """ Clear all Person-related workflow data and logout any User from the current browsing session """
    logout(request)
    for x in [
        'person_id', 'person_setup', 'person_setup_stage', 'auth_person_id', 'rider_setup_state',
        'rider_first_name', 'rider_last_name', 'rider_email', 'rider_phone',
    ]:
        if x in request.session:
            del request.session[x]

class FakePerson:
    exists = False
    active = False
    def can_login(self):
        return False

def get_person(request):
    person_id = request.session.get('person_id')
    if person_id is not None:
        try:
            return Person.objects.get(id=person_id)
        except Person.DoesNotExist:
            pass
    return FakePerson()

class PersonSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        request.person = SimpleLazyObject(lambda: get_person(request))
        return self.get_response(request)