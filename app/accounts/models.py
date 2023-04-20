# https://learndjango.com/tutorials/django-custom-user-model

from django.contrib.auth.models import AbstractUser, UserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.conf import settings
import random, string

class PeddleUser(AbstractUser):
    pass