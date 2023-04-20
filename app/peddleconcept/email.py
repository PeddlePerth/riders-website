from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from smtplib import SMTPException

from .models import PersonToken
import logging

logger = logging.getLogger(__name__)

AUTH_TOKEN_LENGTH = getattr(settings, 'AUTH_TOKEN_LENGTH', 6)
AUTH_TOKEN_VALID_DAYS = getattr(settings, 'AUTH_TOKEN_VALID_DAYS', 1)

CODE_CHARS = '0123456789'
def get_random_code(length):
    return ''.join(random.choice(CODE_CHARS) for _ in range(length))

def send_account_auth_email(person):
    # clear any existing tokens
    tokens = PersonToken.objects.filter(person=person, action='auth_email')
    if (num_tokens := len(tokens)) > 0:
        logger.warning('Clearing %d auth_email tokens for Person %s' % (num_tokens, str(person)))
    tokens.delete()

    token = PersonToken(person=person, action='auth_email', token=get_random_code(AUTH_TOKEN_LENGTH), valid_days=AUTH_TOKEN_VALID_DAYS)

    ctx = {
        'name': person.name,
        'auth_code': token.token,
        'site_url': getattr(settings, 'SITE_BASE_URL'),
    }
    try:
        ok = send_mail(
            'Your Peddle Riders Code is: %s' % token.token,
            render_to_string('email/email_auth.txt', ctx),
            getattr(settings, 'FROM_EMAIL'),
            person.email,
            html_message = render_to_string('email/email_auth.html', ctx),
        )
    except SMTPException:
        ok = False
    
    return bool(ok)
    