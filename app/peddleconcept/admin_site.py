from django.contrib import admin
from peddleconcept.models import Area
from peddleconcept.views.base import base_context

class PeddleAdminSite(admin.AdminSite):
    site_header = 'Peddle Riders Admin'
    site_title = index_title = 'Peddle Riders Admin'

    def each_context(self, request):
        return base_context(
            'admin',
            react = False,
            extra_context = super().each_context(request),
            jsvars = {},
        )
        

admin_site = PeddleAdminSite()

def get_admin_site():
    return admin_site