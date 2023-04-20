from django.contrib import admin

class PeddleAdminSite(admin.AdminSite):
    site_header = 'Peddle Riders Admin'
    site_title = index_title = 'Peddle Riders Admin'

admin_site = PeddleAdminSite()

def get_admin_site():
    return admin_site