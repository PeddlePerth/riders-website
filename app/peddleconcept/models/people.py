from django.db import models
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
import string
from datetime import timedelta

from .base import MutableDataRecord

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
    display_name = models.CharField(max_length=200, verbose_name='Preferred Name')
    email = models.EmailField()
    email_verified = models.BooleanField(blank=True)
    phone = models.CharField(max_length=30, blank=True, verbose_name='Contact Phone Number')

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank = True,
        verbose_name = 'Username for login (Optional)',
        help_text = "Allow this person to login directly with a username/password")
    
    active = models.BooleanField(blank=True)
    abn = models.CharField(max_length=30, blank=True, verbose_name='Contractor ABN')
    bank_bsb = models.CharField(max_length=20, blank=True, verbose_name='Bank account BSB')
    bank_acct = models.CharField(max_length=20, blank=True, verbose_name='Bank account number')
    last_seen = models.DateTimeField(null=True, blank=True)

    # Rider specific data
    RIDER_CLASS_CHOICES = [
        (x, x) for x in ['rider_probationary', 'rider_standard', 'rider_senior', 'rider_professional']
    ]
    rider_class = models.CharField(max_length=20, null=True, blank=True, choices=RIDER_CLASS_CHOICES)
    is_core_rider = models.BooleanField(blank=True, default=False)
    override_pay_rate = models.PositiveIntegerField(null=True, blank=True,
        help_text='Override pay rate for specific rider - LEAVE BLANK unless you are sure!')

    signup_status = models.CharField(max_length=20, choices=(
        ('initial', 'Signed up - has not confirmed email'),
        ('confirmed', 'Signed up - email confirmed'),
        ('complete', 'Signed up - all details completed'),
    ), default='initial')

    @property
    def name(self):
        fullname = ('%s %s' % (self.first_name, self.last_name)).strip()
        return fullname or self.display_name or (self.user.username if self.user else None) or '(no name)'

    def __str__(self):
        return self.name

    def can_login(self):
        return self.active and self.signup_status == 'complete'

    #prefer_bike = models.ForeignKey('Bike', on_delete=models.SET_NULL, null=True, blank=True,
    #    help_text='Preferred bike for riders')

CHARS = string.ascii_letters + string.digits
def get_random_token(length):
    # from https://www.askpython.com/python/examples/generate-random-strings-in-python
    return ''.join(random.choice(CHARS) for _ in range(length))

class PersonToken(models.Model):
    class Meta:
        verbose_name = 'Auth Token (Advanced)'
        verbose_name_plural = 'Auth Tokens (Advanced)'
        
    TOKEN_ACTION_CHOICES = [
        (x, x) for x in ['auth_email', 'login']
    ]
    action = models.CharField(max_length=20, choices=TOKEN_ACTION_CHOICES)
    token = models.CharField(max_length=80, default=get_random_token)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)

    valid_from = models.DateTimeField(auto_now_add=True)
    valid_days = models.PositiveIntegerField(blank=True, default=0, verbose_name='Number of days token is valid')

    def full_login_url(self):
        if self.action == 'login':
            return settings.SITE_BASE_URL + reverse('token_login', args=[self.token])

    def login_url(self):
        if self.action == 'login':
            return reverse('token_login', args=[self.token])

    def is_valid(self):
        if self.valid_days == 0:
            return True
        return self.valid_from + timedelta(days=self.valid_days) < timezone.now()