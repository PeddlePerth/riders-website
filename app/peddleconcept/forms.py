from django import forms
from peddleconcept.models import Person

from django.conf import settings

AUTH_TOKEN_LENGTH = getattr(settings, 'AUTH_TOKEN_LENGTH', 6)

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ('first_name', 'last_name', 'phone', 'email', 'abn', 'bank_bsb', 'bank_acct',)
    
    first_name = forms.CharField(required=True, max_length=100)
    last_name = forms.CharField(required=True, max_length=100)
    phone = forms.CharField(required=True, max_length=30, label='Contact Phone')
    email = forms.EmailField(required=True, max_length=255, label='Contact Email')
    abn = forms.CharField(required=True, max_length=30, label='Rider ABN')
    bank_bsb = forms.CharField(required=True, max_length=10, label='BSB')
    bank_acct = forms.CharField(required=True, max_length=20, label='Account Number')

def get_field(f):
    f.html = f.as_widget(attrs={
        'class': 'form-control' + (' is-invalid' if f.errors else ' is-valid') if f.value else '',
    })
    return f

class PersonProfileForm(forms.ModelForm):
    """ Personal details profile form: changes to email address will require 2-step verification """
    class Meta:
        model = Person
        fields = ('first_name', 'last_name', 'display_name', 'phone', 'email')

    first_name = forms.CharField(required=True, max_length=100)
    last_name = forms.CharField(required=True, max_length=100)
    display_name = forms.CharField(required=True, max_length=20)
    phone = forms.CharField(required=True, max_length=30, label='Mobile Phone')
    email = forms.EmailField(required=True, max_length=255, label='Email Address')

class PayrollProfileForm(forms.ModelForm):
    """ Payroll profile update form: sends an email notification to rider if changes are made """
    class Meta:
        model = Person
        fields = ('abn', 'bank_bsb', 'bank_acct')

    abn = forms.CharField(required=True, max_length=20, label='Your ABN')
    bank_bsb = forms.CharField(required=True, max_length=7, label='Bank BSB')
    bank_acct = forms.CharField(required=True, max_length=20, label='Bank Account Number')

class PersonLoginForm(forms.Form):
    email = forms.EmailField(required=True, max_length=255, label='Email address')

class PersonVerifyCodeForm(forms.Form):
    auth_code = forms.CharField(required=True, max_length=AUTH_TOKEN_LENGTH, label='Enter your %d-digit code' % AUTH_TOKEN_LENGTH)

class RiderSetupForm1(forms.Form):
    first_name = forms.CharField(required=True, max_length=100, label='Your first name')
    last_name = forms.CharField(required=True, max_length=100, label='Your surname')
    email = forms.EmailField(required=True, max_length=255, label='Your best email address')

class RiderSetupForm2(forms.Form):
    phone = forms.CharField(required=True, max_length=30, label='Your phone number (Australia)')
    display_name = forms.CharField(required=True, max_length=20, label='Short display name - your preferred name or initials')
    abn = forms.CharField(required=False, max_length=20, label='Your ABN - if you have one')
    bank_bsb = forms.CharField(required=True, max_length=7, label='Bank Account BSB')
    bank_acct = forms.CharField(required=True, max_length=20, label='Bank Account Number')


