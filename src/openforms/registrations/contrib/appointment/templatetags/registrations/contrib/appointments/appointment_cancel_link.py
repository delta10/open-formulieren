from django import template
from django.utils.safestring import SafeString

from openforms.appointments.base import BasePlugin

register = template.Library()


@register.simple_tag(takes_context=True)
def appointment_cancel_link(context: template.Context) -> SafeString:
    submission = context.get("_submission")
    if not submission:
        return SafeString("")

    cancel_link = BasePlugin.get_cancel_link(submission)
    return SafeString(cancel_link)
