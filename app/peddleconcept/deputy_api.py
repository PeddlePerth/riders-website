import requests
import logging
import json
from django.db import transaction
from peddleconcept.settings import get_deputy_api_setting, DEPUTY_API_SETTING
from peddleconcept.models import Person, Area
from peddleconcept.util import log_response
from django.contrib import messages

from peddleconcept.deputy_objects import *

logger = logging.getLogger(__name__)

class DeputyAPI:
    """ Instantiated to allow making a few Deputy API calls in the scope of a single 'session' """
    def __init__(self, request=None):
        self.request = request
        deputy_conf = get_deputy_api_setting()

        self.token = deputy_conf.get('auth_token')
        self.endpoint = deputy_conf.get('deputy_endpoint_url')
        self.default_company_id = deputy_conf.get('default_company_id')
        self.default_employee_role = deputy_conf.get('default_employee_role_id')

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

    def query_all_areas(self):
        resp = self.post(
            'api/v1/resource/OperationalUnit/QUERY',
            {
                "search": { 
                    "s1": { "field": "Company", "data": self.default_company_id, "type": "eq" },
                },
            })

        return ( parse_operationalunit_json(ou) for ou in resp )
    
    def query_all_employees(self):
        resp = self.get('api/v1/supervise/employee')

        return (
            parse_employee_json(obj) for obj in resp
            if obj.get('Company') == self.default_company_id
        )

    def add_employee(self, person, send_invite=True):
        if person.source_row_id:
            logger.warning('Bad attempt to add an employee for Person %d with SRID=%s' % (
                person.pk, person.source_row_id)
            )
            return
        elif not person.active:
            logger.warning('Ignoring add_employee for inactive Person %d' % person.pk)
            return
        
        logger.info('Adding person "%s" id %d to Deputy. Send invite: %s' % (
            person.name, person.pk, send_invite))
        resp = self.post('api/management/v2/employees', {
            "data": {
                "firstName": person.first_name,
                "lastName": person.last_name,
                "displayName": person.display_name,
                "position": self.default_employee_role_id,
                "primaryLocation": {
                    "id": self.default_company_id,
                },
                "contact": {
                    "email1": person.email,
                    "phone1": person.phone,
                },
                "user": {
                    "sendInvite": send_invite,
                },
            }
        })

        if not isinstance(resp, dict) or resp.get('success') != True:
            logger.warning("Bad response for Deputy add_employee: '%s'" % json.dumps(resp))
            return

        try:
            person.source_row_id = resp.get('result').get('data').get('id')
            person.source_row_state = 'live'
        except:
            logger.warning("cannot get JSON attribute result.data.id for new Employee: data='%s'" % json.dumps(resp))
            return
        
        return person


    @transaction.atomic
    def update_areas(self, areas):
        """
        Uses Deputy Resource API BULK operation to create and match Area rows.
        Note this ASSUMES that Deputy API will return created items in the EXACT order as they are uploaded!
        Returns list of ChangeLogs
        """
        data = self.post(
            'api/v1/resource/OperationalUnit/BULK',
            [ make_operationalunit_json(area, self.default_company_id) for area in areas ]
        )

        if (not isinstance(data, dict) or 'errors' in data
            or 'results' not in data or not isinstance(data['results'], list)
            or len(data['results']) != len(areas)):
            logger.error('Errors received from Deputy OperationalUnit/BULK or empty response')
            logger.debug('response data: %s' % json.dumps(data))
            return False
        
        # update area IDs in database
        changelogs = []
        num_created = 0
        num_updated = 0
        for i in range(len(areas)):
            ou = data['results'][i]
            if not isinstance(ou, dict) or not 'Id' in ou:
                logger.warning('Got invalid OrganisationalUnit from Deputy API: %s' % json.dumps(ou))
                continue
            
            if not areas[i].source_row_id:
                areas[i].source_row_id = str(ou['Id'])
                num_created += 1
            elif areas[i].source_row_id != str(ou['Id']):
                logger.error('Deputy BULK response contains Out Of Order rows!!')
                raise Exception('Deputy API BULK row-order assumption failed')
            else:
                num_updated += 1
            if (chglog := areas[i].mark_source_added()):
                changelogs.append(chglog)

            areas[i].save()
        
        ChangeLog.objects.bulk_create(changelogs)
        logger.info('Bulk area update in Deputy: updated %d, created %d' % (num_updated, num_created))