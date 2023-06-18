import requests
import logging
import json
import uuid
from django.db import transaction
from peddleconcept.settings import get_deputy_api_setting, DEPUTY_API_SETTING
from peddleconcept.models import Person, Area
from peddleconcept.util import log_response
from django.contrib import messages
from django.utils.timezone import get_default_timezone
from datetime import datetime, time

from peddleconcept.deputy_objects import *

logger = logging.getLogger(__name__)

class DeputyAPI:
    """ Instantiated to allow making a few Deputy API calls in the scope of a single 'session' """
    def __init__(self, request=None):
        self.request = request
        deputy_conf = get_deputy_api_setting()

        self.token = deputy_conf.get('auth_token')
        self.endpoint = deputy_conf.get('deputy_endpoint_url')
        self.creator_id = deputy_conf.get('api_creator_id')
        self.default_company_id = deputy_conf.get('company_id')
        self.default_employee_role_id = deputy_conf.get('employee_role_id')

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
            if self.request:
                messages.error(self.request, '%s already has a Deputy account' % person.name)
            logger.warning('Bad attempt to add an employee for Person %s with SRID=%s' % (
                person.pk, person.source_row_id)
            )
            return False
        
        logger.info('Adding person "%s" id %s to Deputy. Send invite: %s' % (
            person.name, person.pk, send_invite))

        contact = {}
        if person.email:
            contact['email1'] = person.email
        if person.phone:
            contact['phone1'] = person.phone
        data = {
            "data": {
                "firstName": person.first_name,
                "lastName": person.last_name,
                "displayName": person.display_name,
                "position": "Employee",
                "primaryLocation": {
                    "id": self.default_company_id,
                },
                "contact": contact,
                "user": {
                    "sendInvite": send_invite,
                },
            }
        }
        logger.debug(json.dumps(data))
        resp = self.post('api/management/v2/employees', data)

        if not isinstance(resp, dict) or resp.get('success') != True:
            logger.warning("Bad response for Deputy add_employee: '%s'" % json.dumps(resp))
            try:
                error = resp.get('error').get('message')
                if self.request:
                    messages.error(self.request, "Could not add Deputy employee %s: %s" % (
                        person.name, error,
                    ))
            except:
                if self.request:
                    messages.error(self.request, "Unexpected/invalid response from Deputy")
            return False

        try:
            person.source_row_id = resp.get('result').get('data').get('id')
            person.source_row_state = 'live'
            logger.info('Created Deputy employee for Person id %s with Deputy ID %s' % (
                person.pk, person.source_row_id,
            ))
            person.save()
            if self.request:
                messages.success(self.request, 'Deputy invitation sent to %s (employee ID %s)' % (
                    person.email, person.source_row_id))
            return True
        except:
            if self.request:
                messages.error(self.request, "Unexpected/invalid response from Deputy")
            logger.warning("cannot get JSON attribute result.data.id for new Employee: data='%s'" % json.dumps(resp))
            return False

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

    def query_leave_unavailability(self, avl_date):
        """
        Run two Resource API queries: Leave and EmployeeAvailability.
        Returns all leave for all employees during that period in the form of:
        { employee_id: [(start_time_unix, end_time_unix, comment), ...] }
        """

        # leave is based on both start and end date
        dpt_leave = self.post('api/v1/resource/Leave/QUERY', {
            "search": {
                "s1": {"field": "DateStart", "type": "le", "data": avl_date.isoformat()}, # AND
                "s2": {"field": "DateEnd", "type": "ge", "data": avl_date.isoformat()},
            },
        })
        # availability is based on schedule but entries are generated for each calculated occurence date
        dpt_unavail = self.post('api/v1/resource/EmployeeAvailability/QUERY', {
            "search": {
                "s1": {"field": "Date", "type": "eq", "data": avl_date.isoformat()},
            },
        })

        employee_time_off = {}
        for leave in dpt_leave:
            emp_id = str(leave['Employee'])
            emp_time = employee_time_off.setdefault(emp_id, [])
            comment = 'on leave'
            if leave['Comment']:
                comment += ' (%s)' % leave['Comment']
            emp_time.append(
                ( 
                    datetime.fromtimestamp(leave['Start']), datetime.fromtimestamp(leave['End']),
                    comment
                )
            )

        for avail in dpt_unavail:
            emp_id = str(avail['Employee'])
            emp_time = employee_time_off.setdefault(emp_id, [])
            comment = 'unavailable'
            if avail['Comment']:
                comment += ' (%s)' % avail['Comment']
            emp_time.append(
                ( 
                    datetime.fromtimestamp(avail['StartTime']), datetime.fromtimestamp(avail['EndTime']),
                    comment
                )
            )
        
        return employee_time_off

    def query_rosters(self, start_date, end_date, area, people_by_srid=None):
        dt_start = datetime.combine(start_date, time(0, 0, 0), tzinfo=get_default_timezone())
        dt_end = datetime.combine(end_date, time(23, 59, 59), tzinfo=get_default_timezone())
        resp = self.post('api/v1/resource/Roster/QUERY', {
            "search": {
                "s1": {"field": "StartTime", "type": "ge", "data": int(dt_start.timestamp()) },
                "s2": {"field": "EndTime", "type": "le", "data": int(dt_end.timestamp()) },
                "s3": {"field": "OperationalUnit", "type": "eq", "data": area.source_row_id },
            }
        })
        
        return [
            parse_roster_json(item, employee_dict=people_by_srid, area_dict={area.id: area}, api_creator_id=self.creator_id)
            for item in resp
        ]

    def add_rosters(self, roster_list):
        """
        BULK upload Roster instances into Deputy Roster objects and record source row IDs.
        Use two calls - first to create rosters using comment field for ID correlation.
        Second call to update comments with actual comment data.
        """

        # assign each roster a unique identifier to identify exactly which ones exist and which ones are errored
        roster_correlation = {}
        for roster in roster_list:
            uid = uuid.uuid4() # random UUID for identifying roster
            roster._shift_notes = roster.shift_notes
            roster_correlation[uid] = roster.shift_notes = str(uid)

        resp = self.post('api/v1/resource/Roster/BULK', [
            make_roster_json(roster) for roster in roster_correlation.values()
        ])

        res = resp.get('results')
        errors = resp.get('errors')
        if isinstance(errors, list):
            logger.warning("Received roster bulk upload error for %d items" % len(errors))

        if isinstance(res, list):
            for dpt_roster in res:
                roster = roster_correlation.get(dpt_roster.get('Comment'))
                if not roster:
                    logger.warning("Missing UUID in comment for Deputy roster, result=%s" % dpt_roster)
                    continue
                roster.source_row_id = dpt_roster.get('Id')
                roster.shift_notes = roster._shift_notes
        
        resp = self.post('api/v1/resource/Roster/BULK', [
            {
                'Id': roster.source_row_id,
                'Comment': roster._shift_notes,
            }
            for roster in roster_correlation.values()
            if roster.source_row_id
        ])

        return list(roster_correlation.values())

    def update_rosters(self, roster_list):
        """ Update the roster objects in Deputy """

        resp = self.post('api/v1/resource/Roster/BULK', [
            make_roster_json(roster) for roster in roster_list
        ])
        if not isinstance(resp, dict):
            return [], []

        res = resp.get('results')
        errors = resp.get('errors')

        if isinstance(errors, list):
            logger.warning("update_rosters got errors for %d rows" % len(errors))
            error_ids = [
                err['resource'].get('Id') for err in errors
            ]
        else:
            error_ids = None
        
        if isinstance(res, list):
            updated_ids = [
                r.get('Id') for r in res
            ]
        else:
            updated_ids = None

        return updated_ids, error_ids

    def delete_rosters(self, roster_ids):
        resp = self.post('api/v1/supervise/roster/discard', {
            'intRosterArray': roster_ids,
        })

        if not isinstance(resp, list):
            return []
        else:
            return [
                item.get('Id') for item in resp
            ]