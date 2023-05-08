import logging, re
import abn

from django import forms
from peddleconcept.models import Person
from peddleconcept.models.people import MOBILE_PHONE_REGEX, BSB_REGEX, BANK_ACCT_REGEX
from accounts.models import PeddleUser
from django.core.exceptions import ValidationError
from django.db.models import Q

from django.conf import settings

logger = logging.getLogger(__name__)

AUTH_TOKEN_LENGTH = getattr(settings, 'AUTH_TOKEN_LENGTH', 6)

def get_form_fields(form):
    form_fields = {}
    for f in form:
        errors = form.errors.get(f.name)
        form_fields[f.name] = {
            'field': f,
            'html': f.as_widget(attrs={
                'class': 'form-control' + (' is-invalid' if errors else ''),
            }),
            'errors': errors,
        }
    return form_fields

class PersonFormMixin:
    def get_instance_filter(self):
        if self.instance is not None and self.instance.id:
            return ~Q(id=self.instance.id)
        else:
            return Q()

    def clean_email(self):
        data = self.cleaned_data.get('email', '').strip()
        if Person.objects.filter(Q(email=data) & self.get_instance_filter()).count() > 0:
            raise ValidationError('Email address already in use')
        return data

    def clean_phone(self):
        data = self.cleaned_data.get('phone', '').strip()
        if not MOBILE_PHONE_REGEX.fullmatch(data):
            raise ValidationError('Please provide a valid Australian mobile phone number')
        if Person.objects.filter(Q(phone=data) & self.get_instance_filter()).count() > 0:
            raise ValidationError('Phone number already taken')
        return data
    
    def clean_display_name(self):
        data = self.cleaned_data.get('display_name', '').strip()
        if Person.objects.filter(Q(display_name=data) & self.get_instance_filter()).count() > 0:
            raise ValidationError('Display name already in use, please choose another one')
        return data

    def clean_bank_bsb(self):
        data = self.cleaned_data.get('bank_bsb', '')
        if not BSB_REGEX.fullmatch(data):
            raise ValidationError('BSB must be exactly 6 digits')
        return data

    def clean_bank_acct(self):
        data = self.cleaned_data.get('bank_acct', '')
        if not BANK_ACCT_REGEX.fullmatch(data):
            raise ValidationError('Must be a number between 4 and 20 digits')
        return data

    def clean_abn(self):
        data = self.cleaned_data.get('abn', '')
        if not data:
            return ''
        if not (valid := abn.validate(data)):
            raise ValidationError('Must be a valid ABN')
        else:
            data = valid
        return data

class PersonProfileForm(PersonFormMixin, forms.ModelForm):
    """ Personal details profile form: changes to email address will require 2-step verification """
    class Meta:
        model = Person
        fields = ('first_name', 'last_name', 'display_name', 'phone', 'abn')

    first_name = forms.CharField(required=True, max_length=100)
    last_name = forms.CharField(required=True, max_length=100)
    display_name = forms.CharField(required=True, max_length=20)
    phone = forms.CharField(required=True, max_length=30, label='Mobile phone')
    email = forms.EmailField(required=True, max_length=255, label='Email address')
    abn = forms.CharField(required=False, max_length=20, label='Your ABN - if you have one')

class PayrollProfileForm(PersonFormMixin, forms.ModelForm):
    """ Payroll profile update form: sends an email notification to rider if changes are made """
    class Meta:
        model = Person
        fields = ('bank_bsb', 'bank_acct')

    bank_bsb = forms.CharField(required=True, max_length=7, label='Bank BSB')
    bank_acct = forms.CharField(required=True, max_length=20, label='Bank Account Number')

class PersonLoginForm(forms.Form):
    email = forms.EmailField(required=True, max_length=255, label='Email address')

class EmailConfirmForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ('email', )
    email = forms.EmailField(required=True, max_length=255, label='Confirm email address')

class AuthCodeForm(forms.Form):
    auth_code = forms.CharField(required=True, max_length=AUTH_TOKEN_LENGTH, label='Enter your %d-digit code' % AUTH_TOKEN_LENGTH)

class RiderSetupBeginForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ('first_name', 'last_name', 'email')
    
    first_name = forms.CharField(required=True, max_length=100, label='Your first name')
    last_name = forms.CharField(required=True, max_length=100, label='Your surname')
    email = forms.EmailField(required=True, max_length=255, label='Your best email address')
    
    def clean(self):
        # check for existing person with same name and/or email:
        # - if a Person is found with signup incomplete, adopt that user as this form's instance
        # - if signup-completed users or Person is found and we don't already have an instance then 
        cleaned_data = super().clean()

        fname = cleaned_data.get('first_name', '').strip()
        lname = cleaned_data.get('last_name', '').strip()
        email = cleaned_data.get('email', '').strip()

        if not self.instance.id:
            try:
                continue_as = Person.objects.get(
                    first_name__iexact = fname,
                    last_name__iexact = lname,
                    email__iexact = email,
                    signup_status__in = ['initial', 'confirmed'],
                )
                self.instance = continue_as
                logger.info('found matching Person id=%d for: (%s, %s, %s)' % (
                    continue_as.id, fname, lname, email
                ))
            except (Person.DoesNotExist, Person.MultipleObjectsReturned):
                pass

        filter_users = Q(first_name__iexact = fname, last_name__iexact = lname) | Q(email__iexact = email)
        filter_persons = filter_users & Q(signup_status='complete')
        if self.instance.id:
            filter_persons &= ~Q(id=self.instance.id)
            if self.instance.user:
                filter_users &= ~Q(id=self.instance.user.id)
        
        num_users = PeddleUser.objects.filter(filter_users).count()
        num_ppl = Person.objects.filter(filter_persons).count()

        if num_users > 0 or num_ppl > 0:
            logger.warning('rider_setup_begin got %d conflicting PeddleUsers, %d conflicting Persons for: (%s, %s, %s)' % (
                num_users, num_ppl, fname, lname, email
            ))
            raise ValidationError('Existing user with same name or email.')
        
        return cleaned_data
        
class RiderSetupProfileForm(PersonFormMixin, forms.ModelForm):
    class Meta:
        model = Person
        fields = ('phone', 'display_name', 'abn', 'bank_bsb', 'bank_acct')
    
    phone = forms.CharField(required=True, max_length=30, label='Your phone number')
    display_name = forms.CharField(required=True, max_length=20, label='Short display name - your preferred name or initials')
    abn = forms.CharField(required=False, max_length=20, label='Your ABN - if you have one')
    bank_bsb = forms.CharField(required=True, max_length=7, label='Bank Account BSB')
    bank_acct = forms.CharField(required=True, max_length=20, label='Bank Account Number')