# scrape Fringe World ticket data from Red61 dashboard
from django.conf import settings
import logging
import requests
import csv

from peddleconcept.util import log_response, add_days

logger = logging.getLogger(__name__)

RED61_BASE_HOSTNAME = getattr(settings, 'RED61_BASE_HOSTNAME', 'red61.com.au')
RED61_INSTANCE_ID = getattr(settings, 'RED61_INSTANCE_ID', 'fw')

null = None
true = True
false = False
SEATS_REPORT_PARAMS = {
	"accessLevel": 1,
	"creationDate": null,
	"id": null,
	"name": null,
	"ownerTitle": null,
	"ownerType": null,
	"params": [
		{
			"id": null,
			"paramTypeCode": "VENUEID",
			"paramTypeId": 27201,
			"values": [
				{
					"id": "0",
					"selected": true,
					"title": "--ANY--"
				}
			]
		},
		{
			"id": null,
			"paramTypeCode": "SUBVENUEID",
			"paramTypeId": 27202,
			"values": [
				{
					"id": "0",
					"selected": true,
					"title": "--ANY--"
				}
			]
		},
		{
			"id": null,
			"paramTypeCode": "EVENTID",
			"paramTypeId": 27203,
			"values": [
				{
					"id": "0",
					"selected": true,
					"title": "--ANY--"
				}
			]
		},
		{
			"id": null,
			"paramTypeCode": "PERFID",
			"paramTypeId": 27204,
			"values": [
				{
					"id": "0",
					"selected": true,
					"title": "--ANY--"
				}
			]
		},
		{
			"id": null,
			"paramTypeCode": "COMPANYID",
			"paramTypeId": 27206,
			"values": [
				{
					"id": "0",
					"selected": true,
					"title": "--ANY--"
				}
			]
		},
		{
			"id": null,
			"paramTypeCode": "PROMOTERID",
			"paramTypeId": 27207,
			"values": [
				{
					"id": "0",
					"selected": true,
					"title": "--ANY--"
				}
			]
		},
		{
			"id": null,
			"paramTypeCode": "MISCOID",
			"paramTypeId": 27208,
			"values": [
				{
					"id": "0",
					"selected": true,
					"title": "--ANY--"
				}
			]
		},
		{
			"id": null,
			"paramTypeCode": "SEASONID",
			"paramTypeId": 27210,
			"values": [
				{
					"id": "-1",
					"selected": true,
					"title": "Active Seasons"
				}
			]
		},
        # cut out PERFENDDATE and PERFSTARTDATE
		{
			"id": null,
			"paramTypeCode": "TRANSSTARTDATE",
			"paramTypeId": 27213,
			"values": [
				{
					"id": "",
					"selected": true,
					"title": "dateTime"
				}
			]
		},
		{
			"id": null,
			"paramTypeCode": "TRANSENDDATE",
			"paramTypeId": 27214,
			"values": [
				{
					"id": "",
					"selected": true,
					"title": "dateTime"
				}
			]
		},
		{
			"id": null,
			"paramTypeCode": "EVENTGROUP",
			"paramTypeId": 27200000,
			"values": [
				{
					"id": "EVENTGROUP",
					"selected": true,
					"title": "Group by event"
				}
			]
		},
		{
			"id": null,
			"paramTypeCode": "PERFORMANCEGROUP",
			"paramTypeId": 27200001,
			"values": [
				{
					"id": "PERFORMANCEGROUP",
					"selected": true,
					"title": "Group by performance"
				}
			]
		},
		{
			"id": null,
			"paramTypeCode": "TRANSACTIONGROUP",
			"paramTypeId": 27200002,
			"values": [
				{
					"id": "TRANSACTIONGROUP",
					"selected": true,
					"title": "Group by transaction"
				}
			]
		},
		{
			"id": null,
			"paramTypeCode": "SUMMARY",
			"paramTypeId": 27200003,
			"values": [
				{
					"id": "SUMMARY",
					"selected": false,
					"title": "Summarise"
				}
			]
		}
	],
	"reportTypeId": 272,
	"type": {
		"description": "This report lists all the reserved seat purchases, with transactions, seats details and access requirements.",
		"id": 272,
		"params": [
			{
				"childIds": [
					27202
				],
				"code": "VENUEID",
				"id": 27201,
				"inputType": "LIST_MULTI",
				"name": "Venue",
				"parentIds": [],
				"seasonFiltered": false
			},
			{
				"childIds": [
					27203
				],
				"code": "SUBVENUEID",
				"id": 27202,
				"inputType": "LIST_MULTI",
				"name": "Sub Venue",
				"parentIds": [
					27201
				],
				"seasonFiltered": false
			},
			{
				"childIds": [
					27204
				],
				"code": "EVENTID",
				"id": 27203,
				"inputType": "LIST_MULTI",
				"name": "Event",
				"parentIds": [
					27202
				],
				"seasonFiltered": true
			},
			{
				"childIds": [],
				"code": "PERFID",
				"id": 27204,
				"inputType": "LIST_MULTI",
				"name": "Performance",
				"parentIds": [
					27203
				],
				"seasonFiltered": true
			},
			{
				"childIds": [],
				"code": "COMPANYID",
				"id": 27206,
				"inputType": "LIST_MULTI",
				"name": "Company",
				"parentIds": [],
				"seasonFiltered": false
			},
			{
				"childIds": [],
				"code": "PROMOTERID",
				"id": 27207,
				"inputType": "LIST_MULTI",
				"name": "Promoter",
				"parentIds": [],
				"seasonFiltered": false
			},
			{
				"childIds": [],
				"code": "MISCOID",
				"id": 27208,
				"inputType": "LIST_MULTI",
				"name": "Organisation",
				"parentIds": [],
				"seasonFiltered": false
			},
			{
				"childIds": [],
				"code": "SEASONID",
				"id": 27210,
				"inputType": "LIST_MULTI",
				"name": "Season",
				"parentIds": [],
				"seasonFiltered": false
			},
			{
				"childIds": [],
				"code": "PERFSTARTDATE",
				"id": 27211,
				"inputType": "DATETIME",
				"name": "Performance Start Date",
				"parentIds": [],
				"seasonFiltered": false
			},
			{
				"childIds": [],
				"code": "PERFENDDATE",
				"id": 27212,
				"inputType": "DATETIME",
				"name": "Performance End Date",
				"parentIds": [],
				"seasonFiltered": false
			},
			{
				"childIds": [],
				"code": "TRANSSTARTDATE",
				"id": 27213,
				"inputType": "DATETIME",
				"name": "Transaction Start Date",
				"parentIds": [],
				"seasonFiltered": false
			},
			{
				"childIds": [],
				"code": "TRANSENDDATE",
				"id": 27214,
				"inputType": "DATETIME",
				"name": "Transaction End Date",
				"parentIds": [],
				"seasonFiltered": false
			},
			{
				"childIds": [],
				"code": "EVENTGROUP",
				"id": 27200000,
				"inputType": "BOOLEAN",
				"name": "Group by event",
				"parentIds": [],
				"seasonFiltered": false
			},
			{
				"childIds": [],
				"code": "PERFORMANCEGROUP",
				"id": 27200001,
				"inputType": "BOOLEAN",
				"name": "Group by performance",
				"parentIds": [],
				"seasonFiltered": false
			},
			{
				"childIds": [],
				"code": "TRANSACTIONGROUP",
				"id": 27200002,
				"inputType": "BOOLEAN",
				"name": "Group by transaction",
				"parentIds": [],
				"seasonFiltered": false
			},
			{
				"childIds": [],
				"code": "SUMMARY",
				"id": 27200003,
				"inputType": "BOOLEAN",
				"name": "Summarise",
				"parentIds": [],
				"seasonFiltered": false
			}
		],
		"title": "Seat Listing With Access Requirement"
	}
}

class Red61Scraper:
    def __init__(self, username, password, red61_instance=RED61_INSTANCE_ID, cookies=None, jwt=None):
        self.username = username
        self.password = password
        self.api_host = "%s.api.%s" % (red61_instance, RED61_BASE_HOSTNAME)
        self.red61_instance = red61_instance
        self.jwt = jwt

        self.session = requests.Session()

        if cookies:
            for k, v in cookies.items():
                if v:
                    self.session.cookies.set(k, v, domain=self.api_host)

    def request_api_url(self, method, url, json=None, **kwargs):
        reports_origin = 'https://%s.reports.%s' % (self.red61_instance, RED61_BASE_HOSTNAME)

        resp = self.session.request(
            method,
            url,
            json = json,
            headers = {
                'Origin': reports_origin,
                'Referer': reports_origin + '/',
            },
            **kwargs)
        log_response(resp, logger=logger)
        return resp

    def get_api_url(self, path):
        return "https://%s/%s/%s" % (self.api_host, self.red61_instance, path)

    def try_login(self):
        login_url = self.get_api_url('api/agency/jwt/login')
        
        login_data = {
            'username': self.username,
            'password': self.password,
        }
        login_resp = self.request_api_url('POST', login_url, json=login_data)
        if login_resp.status_code != 200:
            return False
        
        self.jwt = login_resp.text
        return True

    def run_seats_report(self, start_date, end_date=None):
        """ returns seats report as list of dicts, converted from csv format """
        report_query = SEATS_REPORT_PARAMS

        if not end_date:
            end_date = start_date

        report_query['params'].append({
			"id": null,
			"paramTypeCode": "PERFSTARTDATE",
			"paramTypeId": 27211,
			"values": [
				{
					"id": start_date.strftime("%d/%m/%Y 00:01"), #"14/01/2022 00:00",
					"selected": true,
					"title": "dateTime"
				}
			]
		})

        report_query['params'].append({
			"id": null,
			"paramTypeCode": "PERFENDDATE",
			"paramTypeId": 27212,
			"values": [
				{
					"id": end_date.strftime("%d/%m/%Y 23:59"), #"14/01/2022 23:59",
					"selected": true,
					"title": "dateTime"
				}
			]
		})

        report_url = self.get_api_url('reports/rest/report-types/272/run?dataType=csv')

        # returns data in CSV format
        resp = self.request_api_url('POST', report_url, json=report_query)
        
        csv_lines = ( line for line in resp.text.split('\n') )
        reader = csv.DictReader(csv_lines)

        # finally convert the CSV to an array of dicts
        return [ row for row in reader ]
        
