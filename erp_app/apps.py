from django.apps import AppConfig

class ErpAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'erp_app'

    def ready(self):
        import erp_app.signals
