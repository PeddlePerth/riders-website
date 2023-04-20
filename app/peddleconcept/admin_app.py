from django.contrib.admin.apps import SimpleAdminConfig

class PeddleAdmin(SimpleAdminConfig):
    default_site = 'peddleconcept.admin_site.get_admin_site'

    def ready(self):
        super().ready()
        import peddleconcept.admin
        import accounts.admin