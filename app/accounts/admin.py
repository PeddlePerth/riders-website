from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from admin_action_buttons.admin import ActionButtonsMixin
from django.utils.html import format_html
from django.urls import reverse

from .forms import PeddlerCreationForm, PeddlerChangeForm
from .models import PeddleUser
from peddleconcept.actions import download_as_csv


class ReadOnlyAdmin:
    def has_add_permission(self, request):
        return False

@admin.register(PeddleUser)
class PeddleUserAdmin(UserAdmin):
    add_form = PeddlerCreationForm
    form = PeddlerChangeForm

    actions = [download_as_csv]

admin.site.unregister(Group)