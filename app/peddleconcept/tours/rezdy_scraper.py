# Scrape rezdy manifest data from Rezdy website

import requests
from urllib.parse import urlparse, parse_qs
import os
import json
from datetime import datetime, timedelta, date
from sys import stderr
import logging

from django.conf import settings
from peddleconcept.models import Settings, Tour
from peddleconcept.util import str_response, log_response

logger = logging.getLogger(__name__)

COOKIES_DOMAIN = getattr(settings, 'REZDY_COOKIES_DOMAIN', '.rezdy.com')
REZDY_PROXY = getattr(settings, 'REZDY_PROXY', None)

COOKIES = ('RZDSESSID', 'RZD_PROXY_SESSION', 'PHPSESSIDAPP', 'YII_CSRF_TOKEN', 'rzd_appUserEmail', 'rzd_appUserId', 'rzd_appCompanyId', 'rzd_company_id')


class RezdyScraper:
    def __init__(self, username, password, cookies=None, proxy=REZDY_PROXY, cookies_domain=COOKIES_DOMAIN):
        self.login_error = ''
        self.last_error = ''
        self.profile = None
        self.username = username
        self.password = password
        
        self.session = requests.Session()
        if proxy:
            self.session.proxies = dict(http=proxy, https=proxy)

        if cookies:
            for k, v in cookies.items():
                if v:
                    self.session.cookies.set(k, v, domain=COOKIES_DOMAIN)


    def is_login_required(self, response):
        """ determine if login is required based on an unexpected response from Rezdy app """
        redirect_url = urlparse(response.url)
        return redirect_url.hostname != 'app.rezdy.com'
    
    def try_request_url(self, url, data=None):
        """ try to get the given URL and return correct data, detect if login required """
        try:
            for i in range(3):
                if data:
                    resp = self.session.post(url, data=data)
                else:
                    resp = self.session.get(url)
                log_response(resp, logger=logger)
                
                if self.is_login_required(resp):
                    login_ok = self.login_to_rezdy()
                    if not login_ok:
                        return None
                else:
                    return resp
            self.last_error = "Exceeded maximum retries trying to fetch url: %s" % url
            logger.error(self.last_error)
        except requests.RequestException as e:
            self.last_error = str(e)
            logger.error(self.last_error)

    def request_auth_svc(self, path, auth_svc_params, data=None):
        headers = {
            'Referer': 'https://auth.rezdy.com/',
            'Origin': 'https://auth.rezdy.com',
        }

        url = 'https://svc-auth-container.rezdy.com' + path + '?' + auth_svc_params
        if data:
            resp = self.session.post(url, data=data)
        else:
            resp = self.session.get(url)
        log_response(resp, logger=logger)
        return resp

    def get_auth_svc_redirect_uri(self, auth_svc_response):
        # call the oauthCallback endpoint, this redirects to https://app.rezdy.com/login which redirects to the https://auth.rezdy.com/oauth2/authorize
        try:
            oauth_login_redirect_uri = auth_svc_response.json()['redirect_uri']
            return oauth_login_redirect_uri
        except KeyError:
            self.log_login_error("Couldn't find oauth redirect_uri in login response! Rezdy returned: %s" % auth_svc_response.json())
        except json.JSONDecodeError:
            self.log_login_error("Unexpected response format from Rezdy auth service, aborting. Content-Type: %s" % 
                auth_svc_response.headers['content-type'])

    def request_oauth_redirect_uri(self, redirect_uri):
        resp = self.session.get(redirect_uri, headers={'Referer': 'https://auth.rezdy.com/'})
        log_response(resp)
        return resp

    def login_get_profile(self, auth_svc_params):
        rprof = self.request_auth_svc('/profile', auth_svc_params)

        try:
            profile = rprof.json()
            if 'errorCode' in profile:
                logger.info("Get profile returned errorCode: %s" % profile['errorCode'])
                return False
            logger.info("Fetched Rezdy profile: %s %s (%s)" % (profile['firstname'], profile['lastname'], profile['email']))
            self.profile = profile
            return True
        except Exception as e:
            logger.error("Unexpected response from Rezdy auth service profile endpoint. Content-Type: %s" % rprof.headers['content-type'])
            logger.error(e)
            return False

    def log_login_error(self, errmsg):
        self.login_error = errmsg
        logger.error("Rezdy login failed: %s" % errmsg)

    def login_to_rezdy(self, max_retries=3):
        logger.info("Logging into Rezdy as user %s" % self.username)

        for i in range(max_retries):
            logger.debug("Attempting login to Rezdy. This is attempt %d." % i)
            # CLEAR COOKIES before each login attempt - ensure the session is clean
            logger.debug('Clearing session cookies')
            self.session.cookies.clear()
            # access the website - redirects to https://app.rezdy.com/login which redirects to
            # https://auth.rezdy.com/oauth2/authorize?action=login&state=...&scope=&response_type=code&approval_prompt=auto&redirect_uri=
            #      https://app.rezdy.com/auth/oauthCallback&client_id=...&code_challenge=[...]

            # or if the session has expired: https://app.rezdy.com/ redirects -> https://app.rezdy.com/logout -> https://auth.rezdy.com/logout

            r = self.session.get('https://app.rezdy.com/')
            log_response(r)

            redirect_url = urlparse(r.url)
            if redirect_url.hostname == 'app.rezdy.com':
                # already logged in!
                logger.info("No need to login, already authenticated.")
                return True
            elif redirect_url.hostname == 'auth.rezdy.com':
                if redirect_url.path == '/oauth2/authorize':
                    logger.debug("Redirected to login site, proceeding with login")
                elif redirect_url.path == '/logout':
                    logger.info("Session expired, redirected to logout page. Retrying.")
                    continue
                else:
                    logger.warning("Rezdy app redirected to unexpected location, retrying: %s" % r.url)
                    continue

            # get the magic URL query string containing oauth state and various challenge params
            auth_svc_params = redirect_url.query
            logger.debug("Got auth_svc_params '%s'" % auth_svc_params)

            # try getting the profile, returns 200 if we are authenticated with the svc-auth-rezdy endpoint, 401 if not
            profile_ok = self.login_get_profile(auth_svc_params)

            # POST login credentials to svc-auth-rezdy, returns 200 on success and returns a json: 
            # redirect_uri: https://app.rezdy.com/auth/oauthCallback?state=...&code=...
            login_info = {
                'username': self.username,
                'password': self.password,
            }
            rlogin = self.request_auth_svc('/login', auth_svc_params, data=login_info)
            if rlogin.status_code != 200:
                self.log_login_error("Unable to login to Rezdy, check username/password. Rezdy returned: %s" % rlogin.content)
                return False

            # parse the request_uri from the response data (aka oauthCallback URL)
            oauth_login_redirect_uri = self.get_auth_svc_redirect_uri(rlogin)
            if not oauth_login_redirect_uri:
                return False # already logged the error

            logger.info("Stage 1 OK: got login redirect_uri: %s" % oauth_login_redirect_uri)

            # GET the redirect_uri (oauthCallback) redirects to https://app.rezdy.com/login which 
            # redirects to https://auth.rezdy.com/oauth2/authorize
            rlogin_auth = self.request_oauth_redirect_uri(oauth_login_redirect_uri)

            # get the URL query parameters from the redirected authorize URL, then send it to the svc-auth-container authorize endpoint
            auth_svc_params = urlparse(rlogin_auth.url).query

            # check we are authenticated with svc-auth-rezdy, should definitely work this time
            profile_ok = self.login_get_profile(auth_svc_params)
            if not profile_ok:
                self.log_login_error("Unable to fetch profile after successful login! Aborting.")
                return False

            # call svc-auth-rezdy authorize endpoint after login OK, this will return a json with another redirect_uri
            rauth = self.request_auth_svc('/oauth2/authorize', auth_svc_params)

            oauth_authorize_redirect_uri = self.get_auth_svc_redirect_uri(rauth)
            if not oauth_authorize_redirect_uri:
                return False

            logger.info("Stage 2 OK: got authorize redirect_uri: %s" % oauth_authorize_redirect_uri)

            # now access the redirect_uri from the oauth2 authorize endpoint
            rauth_redirect = self.request_oauth_redirect_uri(oauth_authorize_redirect_uri)

            success_url = urlparse(rauth_redirect.url)
            if success_url.hostname == 'app.rezdy.com':
                logger.info("Login success! Redirected to Rezdy app.")
                return True
            
            logger.warning("Login redirected to unexpected location, retrying: %s" % success_url)
        
        self.log_login_error("Login failed: Reached maximum login retries")
        return False

    def fetch_manifest_data(self, manifest_date=None):
        url = 'https://app.rezdy.com/calendar/generateManifestDataAjax'
        manifest_date = date.today() if not manifest_date else manifest_date
        manifest_opts = {
            "GridSetting[startDate]": manifest_date.isoformat(),
            "YII_CSRF_TOKEN": self.session.cookies.get('YII_CSRF_TOKEN', None),
            "GridSetting[groupBy]": "SESSION",
            "GridSetting[orderStatuses][]": "CONFIRMED",
            "GridSetting[visibleColumns][]": [ "order-internal-notes", "order-number", "order-special-requirements", "participants-list", "extras", "pick-up-location", "pick-up-time", "product", "quantities", "session", "session-end", "customer-full-name", "customer-phone" ],
            "GridSetting[company][id]": "167604",
            "GridSetting[id]": "8057",
            "GridSetting[quickFilters]": "{}",
            "GridSetting[columnOrders]": "{\"product\":0,\"session\":1,\"session-end\":2,\"customer-full-name\":3,\"customer-phone\":4,\"participants-list\":5,\"quantities\":6,\"order-special-requirements\":7,\"pick-up-location\":8,\"extras\":9,\"order-internal-notes\":10,\"pick-up-time\":11,\"order-number\":12}",
            "GridSetting[columnSizes]": "{\"product\":140,\"session\":72,\"session-end\":115,\"customer-full-name\":119,\"customer-phone\":104,\"participants-list\":140,\"quantities\":140,\"order-special-requirements\":190,\"pick-up-location\":100,\"extras\":140,\"order-internal-notes\":140,\"pick-up-time\":69,\"order-number\":140}",
            "GridSetting[sorting]": "{}",
        }
        resp = self.try_request_url(url, data=manifest_opts)
        if not resp:
            return None

        try:
            manifest_data = resp.json()
            return manifest_data
        except json.JSONDecodeError:
            self.last_error = "Manifest data not in JSON format! Content-Type: %s" % resp.headers['content-type']
            logger.error(self.last_error)

    def close(self):
        self.session.close()

    def get_last_error(self):
        return self.login_error or self.last_error