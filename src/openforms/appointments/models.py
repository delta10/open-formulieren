from datetime import date

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.timezone import localdate
from django.utils.translation import gettext_lazy as _

from solo.models import SingletonModel

from .constants import AppointmentDetailsStatus
from .fields import AppointmentBackendChoiceField


class AppointmentsConfig(SingletonModel):
    plugin = AppointmentBackendChoiceField(_("appointment plugin"), blank=True)
    limit_to_location = models.CharField(
        _("location"),
        max_length=50,
        blank=True,
        help_text=_(
            "If configured, only products connected to this location are exposed. "
            "Additionally, the user can only select this location for the appointment."
        ),
    )

    class Meta:
        verbose_name = _("Appointment configuration")

    def save(self, *args, **kwargs):
        if not self.plugin and self.limit_to_location:
            self.limit_to_location = ""
        super().save(*args, **kwargs)


class AppointmentInfo(models.Model):

    status = models.CharField(
        _("status"),
        choices=AppointmentDetailsStatus.choices,
        max_length=50,
    )
    appointment_id = models.CharField(
        _("appointment ID"),
        max_length=64,
        blank=True,
    )
    error_information = models.TextField(
        _("error information"),
        blank=True,
    )
    start_time = models.DateTimeField(
        _("start time"),
        blank=True,
        null=True,
        help_text=_("Start time of the appointment"),
    )

    submission = models.OneToOneField(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="appointment_info",
        help_text=_("The submission that made the appointment"),
    )

    created = models.DateTimeField(
        _("created"),
        auto_now_add=True,
        help_text=_("Timestamp when the appointment details were created"),
    )

    class Meta:
        verbose_name = _("Appointment information")
        verbose_name_plural = _("Appointment information")

    def __str__(self):
        status = self.get_status_display()
        description = self.appointment_id or self.error_information[:20]
        return f"{status}: {description}"

    def cancel(self):
        self.status = AppointmentDetailsStatus.cancelled
        self.save()


class Appointment(models.Model):
    """
    Register details for an appointment.

    This overlaps slightly with :class:`AppointmentInfo`, but is a new take on the
    appointments flow, see https://github.com/open-formulieren/open-forms#2471.

    We register the data submitted from the frontend so that it can be processed (and
    retried) with Celery in an asynchronous way. This records the raw (but validated)
    user input.

    TODO: incorporate the `AppointmentInfo` fields and deprecate that model?
    """

    submission = models.OneToOneField(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="appointment",
        help_text=_("The submission that made the appointment"),
    )
    plugin = AppointmentBackendChoiceField(
        _("plugin"),
        help_text=_(
            "The plugin active at the time of creation. This determines the context "
            "to interpret the submitted data."
        ),
    )
    location = models.CharField(
        _("location ID"),
        max_length=128,
        help_text=_("Identifier of the location in the selected plugin."),
    )
    datetime = models.DateTimeField(
        _("appointment time"),
        help_text=_("Date and time of the appointment"),
    )
    contact_details_meta = models.JSONField(
        _("contact details meta"),
        default=list,
        help_text=_(
            "Contact detail field definitions, depending on the required fields in the "
            "selected plugin. Recorded for historical purposes."
        ),
    )
    contact_details = models.JSONField(
        _("contact details"),
        default=dict,
        help_text=_("Additional contact detail field values."),
    )

    class Meta:
        verbose_name = _("appointment")
        verbose_name_plural = _("appointments")

    @property
    def date(self) -> date:
        # this assumes our timezone is the same timezone as the appointment system
        return localdate(self.datetime)


class AppointmentProduct(models.Model):
    """
    Describe a single product/service ordered for the appointment.

    Depending on the plugin used, one or multiple products may be ordered during
    appointment creation, and each product may have one or more people ('amount').
    """

    appointment = models.ForeignKey(
        "Appointment",
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name=_("appointment"),
        help_text=_("Appointment for this product order."),
    )
    product_id = models.CharField(
        _("product ID"),
        max_length=128,
        help_text=_("Identifier of the product in the selected plugin."),
    )
    amount = models.PositiveSmallIntegerField(
        _("amount"),
        help_text=_("Number of times (amount of people) the product is ordered"),
        validators=[MinValueValidator(1)],
    )

    class Meta:
        verbose_name = _("appointment product")
        verbose_name_plural = _("appointment products")
