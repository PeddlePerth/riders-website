from django.utils.functional import SimpleLazyObject
from peddleconcept.models import Person
from django.conf import settings

SESSION_MIN_AGE = getattr(settings, 'SESSION_COOKIE_AGE', 3600*24*14) // 2

def get_person(request):
    person_id = request.session.get('person_id')
    if person_id is not None:
        try:
            return Person.objects.get(id=person_id, active__exact=True)
        except Person.DoesNotExist:
            pass

class PersonSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        request.person = SimpleLazyObject(lambda: get_person(request))
        return self.get_response(request)