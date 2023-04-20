from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from .models import PeddleUser

class TokenWidget(forms.Widget):
    class Media:
        js = ('admin/js/vendor/jquery/jquery.js', 'script/token_widget.js', )
    template_name = 'widgets/token.html'


class PeddlerCreationForm(UserCreationForm):
    class Meta:
        model = PeddleUser
        fields = ('username', 'email')
        widgets = {
            'login_token': TokenWidget,
        }

class PeddlerChangeForm(UserChangeForm):
    class Meta:
        model = PeddleUser
        fields = ('username', 'email')
        widgets = {
            'login_token': TokenWidget,
        }