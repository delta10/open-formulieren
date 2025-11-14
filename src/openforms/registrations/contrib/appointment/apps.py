from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AppointmentAppConfig(AppConfig):
    name = "openforms.registrations.contrib.appointment"
    label = "registrations_appointment"
    verbose_name = _("Appointment registration")

    def ready(self):
        from . import plugin  # noqa
