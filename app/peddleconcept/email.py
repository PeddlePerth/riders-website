from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib import messages
from smtplib import SMTPException
import secrets
from datetime import datetime

from .models import PersonToken
import logging

logger = logging.getLogger(__name__)

AUTH_TOKEN_LENGTH = getattr(settings, 'AUTH_TOKEN_LENGTH', 6)
AUTH_TOKEN_VALID_MINUTES = getattr(settings, 'AUTH_TOKEN_VALID_MINUTES', 30)
AUTH_EMAIL_RETRY_SECONDS = getattr(settings, 'AUTH_EMAIL_RETRY_SECONDS', 10)

CODE_CHARS = '0123456789'
def get_random_code(length):
    return ''.join(secrets.choice(CODE_CHARS) for _ in range(length))

def send_account_auth_email(request, name, email):
    """ Generate random token, store token in session, and send email - with timeout to prevent accidental spam """
    token = get_random_code(AUTH_TOKEN_LENGTH)
    now = int(datetime.now().timestamp())
    if 'auth_token' in request.session:
        # check timeout on existing token
        prev_time = int(request.session.get('auth_token_timestamp', 0))
        if now < prev_time + 10:
            messages.warning(request, 'Cannot send auth code emails more than once every %d seconds' % AUTH_EMAIL_RETRY_SECONDS)
            return False

    ctx = {
        'name': name,
        'auth_code': token,
        'valid_minutes': AUTH_TOKEN_VALID_MINUTES,
        'site_url': getattr(settings, 'SITE_BASE_URL'),
    }
    try:
        ok = send_mail(
            'Your Peddle Riders Code is: %s' % token,
            render_to_string('email/email_auth.txt', ctx),
            getattr(settings, 'DEFAULT_FROM_EMAIL'),
            [email],
            html_message = render_to_string('email/email_auth.html', ctx),
        )
        request.session['auth_token'] = token
        request.session['auth_token_timestamp'] = str(now)

        messages.success(request, 'Authentication code sent. Please check your inbox.')
    except SMTPException as e:
        logger.error('Error sending email: %s: %s' % (type(e), e))
        messages.error(request, 
        'Error sending auth code email. Check your details are correct and try again. (%s)' % (
            type(e).__name__))
        ok = False
    
    return bool(ok)

def validate_auth_token(request, token):
    """ Validate token for a particular request """
    if not ('auth_token' in request.session and 'auth_token_timestamp' in request.session):
        return False
        
    now = int(datetime.now().timestamp())
    sess_token = request.session['auth_token']
    token_timestamp = int(request.session['auth_token_timestamp'])

    if sess_token == token and now < token_timestamp + AUTH_TOKEN_VALID_MINUTES * 60:
        del request.session['auth_token']
        del request.session['auth_token_timestamp']
        return True

    return False

def send_payroll_change_email(person):
    ctx = {
        'name': person.name,
        'site_url': getattr(settings, 'SITE_BASE_URL'),
    }
    try:
        ok = send_mail(
            'Peddle payroll details updated',
            render_to_string('email/payroll_change.txt', ctx),
            getattr(settings, 'DEFAULT_FROM_EMAIL'),
            [person.email],
            html_message = render_to_string('email/payroll_change.html', ctx),
        )
    except SMTPException as e:
        logger.error('Error sending email: %s: %s' % (type(e), e))
        ok = False
    
    return bool(ok)