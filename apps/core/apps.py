from django.apps import AppConfig
import decimal

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        # Set precision high enough to comfortably hold max_digits + padding
        decimal.getcontext().prec = 110