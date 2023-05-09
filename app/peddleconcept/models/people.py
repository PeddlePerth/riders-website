from django.db import models
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django.core.validators import RegexValidator
import string
from datetime import timedelta
import secrets
import abn
import re

from .base import MutableDataRecord

MOBILE_PHONE_REGEX = re.compile(r'^(\+614|04|00614)\d{8}$')
BSB_REGEX = re.compile(r'^\d{3}-?\d{3}$')
BANK_ACCT_REGEX = re.compile(r'^\d{4,20}$')

def validate_abn(value):
    if value and not abn.validate(value):
        return False
    return True

class Person(MutableDataRecord):
    """
    Model representing a tour operator (rider) or other staff member.
    Corresponds 1:1 with Deputy Employees.
    """
    class Meta:
        verbose_name_plural = 'People'

    MUTABLE_FIELDS = ('first_name', 'last_name', 'display_name', 'email', 'active')
    first_name = models.CharField(max_length=200)
    last_name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200, unique=True, null=True, verbose_name='Preferred Name', 
        error_messages={
            'unique': 'Display name already taken',
            'blank': 'Display name cannot be blank',
        })
    email = models.EmailField(unique=True, null=True, error_messages={
        'unique': 'Email address already in use',
        'blank': 'You must enter an email address',
    })
    email_verified = models.BooleanField(blank=True, default=False)
    phone = models.CharField(max_length=30, unique=True, null=True, verbose_name='Contact Phone Number',
        error_messages={
            'unique': 'Phone number already taken',
            'blank': 'You must enter a phone number',
        },
        validators = [RegexValidator(MOBILE_PHONE_REGEX, message='Please provide a valid Australian mobile phone number')],
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank = True,
        verbose_name = 'Username for login (Optional)',
        help_text = "Allow this person to login directly with a username/password")
    
    active = models.BooleanField(blank=True)
    abn = models.CharField(max_length=30, blank=True, verbose_name='Contractor ABN',
        validators=[validate_abn])
    bank_bsb = models.CharField(max_length=20, blank=True, verbose_name='Bank account BSB',
        validators = [RegexValidator(BSB_REGEX, message='BSB must be exactly 6 digits')],
    )
    bank_acct = models.CharField(max_length=20, blank=True, verbose_name='Bank account number',
        validators = [RegexValidator(BANK_ACCT_REGEX, message='Must be a number between 4 and 20 digits')]
    )
    last_seen = models.DateTimeField(default=timezone.now, null=True, blank=True, verbose_name='Last activity')
    created = models.DateTimeField(default=timezone.now, verbose_name='Date joined')

    # Rider specific data
    RIDER_CLASS_CHOICES = [
        ('rider_probationary', 'Probationary Rider (noob)'),
        ('rider_standard', 'Standard Rider'),
        ('rider_senior', 'Senior Rider'),
        ('rider_professional', 'Pro Rider'),
    ]
    rider_class = models.CharField(max_length=20, null=True, blank=True, choices=RIDER_CLASS_CHOICES)
    is_core_rider = models.BooleanField(blank=True, default=False)
    override_pay_rate = models.PositiveIntegerField(null=True, blank=True,
        help_text='Override pay rate for specific rider - LEAVE BLANK unless you are sure!')

    signup_status = models.CharField(max_length=20, choices=(
        ('migrated', 'Migrated account - verification needed'), # migrated -> confirmed
        ('confirmed', 'Signed up - email confirmed'), # confirmed -> complete
        ('complete', 'Signed up - all details completed'),
    ), default='migrated')

    @property
    def name(self):
        fullname = ('%s %s' % (self.first_name, self.last_name)).strip()
        return fullname or self.display_name or (self.user.username if self.user else None) or '(no name)'

    def __str__(self):
        return self.name

    def can_login(self):
        return self.active and self.signup_status in ('complete', 'migrated')

    def phone_valid(self):
        return MOBILE_PHONE_REGEX.fullmatch(self.phone)

    def abn_valid(self):
        return abn.validate(self.abn) != False

    def bank_details_valid(self):
        return BSB_REGEX.fullmatch(self.bank_bsb) and BANK_ACCT_REGEX.fullmatch(self.bank_acct)

    def profile_complete(self):
        return (
            self.display_name and self.email_verified
            and self.phone_valid()
            and self.abn_valid()
            and self.bank_details_valid()
            and self.signup_status == 'complete'
        )

    def pay_rate(self):
        if self.override_pay_rate:
            return self.override_pay_rate
        from peddleconcept.settings import get_rider_payrate_setting
        return get_rider_payrate_setting().get(self.rider_class, 30)

    def rider_class_label(self):
        for x, y in self.RIDER_CLASS_CHOICES:
            if x == self.rider_class:
                return y

    def bank_details_text(self):
        if self.bank_details_valid():
            return 'Account number ending in %s' % (self.bank_acct[:3])
        else:
            return 'Not provided'
    
    exists = True # see middleware.py

def get_random_token():
    return secrets.token_urlsafe(42)

class PersonToken(models.Model):
    """ Database-backed URL tokens corresponding to a particular action, ie. for a particular Person object """
    class Meta:
        verbose_name = 'Magic Token (Advanced)'
        verbose_name_plural = 'Magic Tokens (Advanced)'
        
    TOKEN_ACTION_CHOICES = [
        # Create a generic "signup invitation" URL with a particular random token
        ('rider_invite_generic', 'Rider signup invitation URL'),
        # Existing rider login URLs are converted to this type
        ('rider_login_migrated', 'Migrated rider login URL'), 
    ]
    action = models.CharField(max_length=30, choices=TOKEN_ACTION_CHOICES)
    token = models.CharField(max_length=80, default=get_random_token)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, null=True)

    valid_from = models.DateTimeField(auto_now_add=True)
    valid_days = models.PositiveIntegerField(blank=True, default=0, 
        verbose_name='Number of days token is valid (0 = forever)')

    def full_url(self):
        return settings.SITE_BASE_URL + self.url

    @property
    def url(self):
        if self.action == 'rider_login_migrated':
            return reverse('token_login_migrate', args=[self.token])
        elif self.action == 'rider_invite_generic':
            return reverse('rider_setup_invite', args=[self.token])

    def is_valid(self):
        if self.valid_days == 0:
            return True
        return self.valid_from + timedelta(days=self.valid_days) > timezone.now()