import requests
import logging
from peddleconcept.settings import get_deputy_api_setting, get_deputy_defaults_setting, DEPUTY_API_SETTING
from peddleconcept.models import Person, Area
from peddleconcept.util import log_response
from django.contrib import messages

logger = logging.getLogger(__name__)

class DeputyAPI:
    """ Instantiated to allow making a few Deputy API calls in the scope of a single 'session' """
    def __init__(self, request=None):
        self.request = request
        deputy_conf = get_deputy_api_setting()
        deputy_defaults = get_deputy_defaults_setting()

        self.token = deputy_conf.get('auth_token')
        self.endpoint = deputy_conf.get('endpoint_url')

        if not self.token:
            logger.error('Deputy API cannot be used without endpoint and auth token: make sure %s is configured in Settings' % 
                DEPUTY_API_SETTING)
            if request:
                messages.error(request, 'Deputy API is not configured: please check %s in Settings' % DEPUTY_API_SETTING)
    
    def make_url(self, url):
        return '%s/%s' % (self.endpoint, url)

    def get(self, url):
        full_url = self.make_url(url)
        resp = requests.get(full_url, headers={
            'Accept': 'application/json',
            'Authorization': 'Bearer %s' % self.token,
        })
        log_response(resp)
        return resp.json()

    def post(self, url, data):
        full_url = self.make_url(url)
        resp = requests.post(full_url, json=data, headers={
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % self.token,
        })
        log_response(resp)
        return resp.json()
    

def sync_areas(api, areas_qs):
    """ Synchronise Area/OperationalUnit objects between Local DB and Deputy API """
    db_areas = {
        area.source_row_id: area for area in areas_qs
    }

    deputy_areas_resp = api.post('api/v1/resource/OperationalUnit/QUERY')
    
    