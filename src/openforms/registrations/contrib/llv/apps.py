from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class LLVAppConfig(AppConfig):
    name = "openforms.registrations.contrib.llv"
    label = "registrations_llv"
    verbose_name = _("LLV registration")

    def ready(self):
        from . import plugin  # noqa
