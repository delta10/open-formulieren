import json
import logging
from datetime import datetime
from typing import Any, override
from urllib.parse import urljoin

from django.core.exceptions import SuspiciousOperation
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.timezone import make_aware
from django.utils.translation import gettext_lazy as _

from zgw_consumers.client import build_client

from ...exceptions import RegistrationFailed

from openforms.appointments.constants import AppointmentDetailsStatus
from openforms.appointments.core import book
from openforms.appointments.exceptions import AppointmentCreateFailed
from openforms.appointments.models import Appointment, AppointmentInfo, AppointmentProduct
from openforms.appointments.utils import get_plugin as get_appointment_plugin
from openforms.logging import logevent
from openforms.submissions.constants import RegistrationStatuses
from openforms.submissions.models import Submission, SubmissionReport

from ...base import BasePlugin  # openforms.registrations.base
from ...registry import register  # openforms.registrations.registry
from .config import AppointmentOptionsSerializer

logger = logging.getLogger(__name__)

PLUGIN_IDENTIFIER = 'appointment'


@register(PLUGIN_IDENTIFIER)
class AppointmentRegistration(BasePlugin):
    verbose_name = _("Appointment")
    configuration_options = AppointmentOptionsSerializer

    def _check_response(self, response, operation_name: str):
        """Check response and raise RegistrationFailed if not successful."""
        if not response.ok:
            error_info = f"{operation_name} failed with status {response.status_code}"
            try:
                response_data = response.json()
                error_info += f" Response: {response_data}"
            except (ValueError, json.JSONDecodeError):
                if hasattr(response, 'text'):
                    error_info += f" Response body: {response.text}"
            raise RegistrationFailed(error_info)

    def register_submission(self, submission: Submission, options: dict) -> dict:
        state = submission.load_submission_value_variables_state()
        form_data = state.get_data()
        form_static_data = state.get_static_data()
        appointment_plugin = get_appointment_plugin()

        # Check if appointment was already created successfully in a previous attempt
        existing_result = submission.registration_result or {}
        appointment_already_created = existing_result.get("appointment_id") is not None

        if not appointment_already_created:
            # Parse datetime and make it timezone-aware
            naive_datetime = datetime.strptime(f"{form_data.get('afspraakDatum')} {form_data.get('afspraakTijd')}", "%Y-%m-%d %H:%M")
            aware_datetime = make_aware(naive_datetime)

            # Build contact details from form data
            contact_details = {}
            if firstName := form_data.get('afspraakVoornaam'):
                contact_details['firstName'] = firstName
            if lastName := form_data.get('afspraakAchternaam'):
                contact_details['lastName'] = lastName
            if email := form_data.get('afspraakEmail'):
                contact_details['email'] = email
            if phone := form_data.get('afspraakTelefoonnummer'):
                contact_details['phone'] = phone
            if identificationNumber := form_data.get('afspraakIdentificatieNummer'):
                contact_details['identificationNumber'] = identificationNumber
            if externalId := form_data.get('afspraakExternID'):
                contact_details['externalId'] = externalId
            if dateOfBirth := form_data.get('afspraakGeboortedatum'):
                contact_details['dateOfBirth'] = dateOfBirth

            # Create Appointment object
            appointment = Appointment.objects.create(
                submission=submission,
                plugin=appointment_plugin.identifier,
                location=form_data.get("afspraakBranchId"),
                datetime=aware_datetime,
                contact_details=contact_details,
                contact_details_meta=[],
            )

            AppointmentProduct.objects.create(
                appointment=appointment,
                product_id=form_data.get("afspraakServiceId"),
                amount=1,
            )

            # Delete previous appointment info if exists
            AppointmentInfo.objects.filter(submission=submission).delete()

            try:
                appointment_id = book(appointment, form_data.get('afspraakOpmerkingen', ''))
                result: dict[str, Any] = {"appointment_id": appointment_id, "status": "success"}
                submission.save_registration_status(RegistrationStatuses.in_progress, result)
            except AppointmentCreateFailed as e:
                logger.error("Appointment creation failed", exc_info=e)
                # This is displayed to the end-user!
                error_information = _(
                    "A technical error occurred while we tried to book your appointment. "
                    "Please verify if all the data is correct or try again later."
                )
                appointment_info = AppointmentInfo.objects.create(
                    status=AppointmentDetailsStatus.failed,
                    error_information=error_information,
                    submission=submission,
                )
                logevent.appointment_register_failure(appointment_info, appointment_plugin, e)
                raise RegistrationFailed("Unable to create appointment") from e
        else:
            # Reuse existing appointment result
            logger.info("Appointment already created, skipping appointment creation")
            result: dict[str, Any] = {
                "appointment_id": existing_result["appointment_id"],
                "status": existing_result.get("status", "success"),
            }

        # After successfully booking the appointment, trigger the second registration backend
        registration_backends = list(submission.form.registration_backends.all())
        if len(registration_backends) > 1:
            second_backend = registration_backends[1]
            logger.info(f"Triggering second registration backend: {second_backend.backend}")

            # Get the plugin for the second backend
            registry = second_backend._meta.get_field("backend").registry
            second_plugin = registry[second_backend.backend]

            # Validate and prepare options
            options_serializer = second_plugin.configuration_options(
                data=second_backend.options,
                context={"validate_business_logic": False},
            )

            if options_serializer.is_valid():
                # Register with the second backend
                try:
                    second_result = second_plugin.register_submission(
                        submission, options_serializer.validated_data
                    )
                    logger.info(f"Second registration completed: {second_result}")
                    # Add second registration result to the main result
                    result["second_registration"] = {
                        "backend": second_backend.backend,
                        "result": second_result,
                    }
                except Exception as e:
                    logger.error(f"Second registration failed: {e}", exc_info=e)
                    # Fail the whole registration if second backend fails
                    result["second_registration"] = {
                        "backend": second_backend.backend,
                        "error": str(e),
                    }
                    raise RegistrationFailed(f"Second registration backend failed: {e}") from e
            else:
                logger.error(f"Second backend options invalid: {options_serializer.errors}")
                result["second_registration"] = {
                    "backend": second_backend.backend,
                    "error": "Invalid options",
                    "validation_errors": options_serializer.errors,
                }
                raise RegistrationFailed(f"Second registration backend has invalid options: {options_serializer.errors}")

        return result

    def check_config(self) -> None:
        # Config checks are not really relevant for this plugin right now
        pass

    @override
    def get_custom_templatetags_libraries(self) -> list[str]:
        prefix = "openforms.registrations.contrib.appointment.templatetags.registrations.contrib"
        return [
            f"{prefix}.appointments.appointment_cancel_link",
        ]
