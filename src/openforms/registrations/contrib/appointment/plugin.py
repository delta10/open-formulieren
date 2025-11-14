import json
from datetime import datetime
from typing import Any, override

from django.utils.timezone import make_aware
from django.utils.translation import gettext_lazy as _

import structlog

from openforms.appointments.constants import AppointmentDetailsStatus
from openforms.appointments.core import book
from openforms.appointments.exceptions import AppointmentCreateFailed
from openforms.appointments.models import (
    Appointment,
    AppointmentInfo,
    AppointmentProduct,
)
from openforms.appointments.utils import get_plugin as get_appointment_plugin
from openforms.forms.models import FormRegistrationBackend
from openforms.logging import audit_logger
from openforms.submissions.constants import RegistrationStatuses
from openforms.submissions.models import Submission

from ...base import BasePlugin  # openforms.registrations.base
from ...exceptions import RegistrationFailed
from ...registry import register  # openforms.registrations.registry
from .config import AppointmentOptionsSerializer

logger = structlog.stdlib.get_logger(__name__)

PLUGIN_IDENTIFIER = "appointment"


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
                if hasattr(response, "text"):
                    error_info += f" Response body: {response.text}"
            raise RegistrationFailed(error_info)

    def book_appointment(self, submission: Submission) -> dict:
        """
        Book synchronously so unavailable slots can be reported before completion.

        Persist the appointment ID for the subsequent asynchronous registration.
        """
        state = submission.load_submission_value_variables_state()
        form_data = state.get_data()
        appointment_plugin = get_appointment_plugin()

        # Check if appointment was already created successfully in a previous attempt
        existing_result = submission.registration_result or {}
        appointment_already_created = existing_result.get("appointment_id") is not None

        if not appointment_already_created:
            # Parse datetime and make it timezone-aware
            naive_datetime = datetime.strptime(
                f"{form_data.get('afspraakDatum')} {form_data.get('afspraakTijd')}",
                "%Y-%m-%d %H:%M",
            )
            aware_datetime = make_aware(naive_datetime)

            # Build contact details from form data
            contact_details = {}
            if firstName := form_data.get("afspraakVoornaam"):
                contact_details["firstName"] = firstName
            if lastName := form_data.get("afspraakAchternaam"):
                contact_details["lastName"] = lastName
            if email := form_data.get("afspraakEmail"):
                contact_details["email"] = email
            if phone := form_data.get("afspraakTelefoonnummer"):
                contact_details["phone"] = phone
            if identificationNumber := form_data.get("afspraakIdentificatieNummer"):
                contact_details["identificationNumber"] = identificationNumber
            if externalId := form_data.get("afspraakExternID"):
                contact_details["externalId"] = externalId
            if dateOfBirth := form_data.get("afspraakGeboortedatum"):
                contact_details["dateOfBirth"] = dateOfBirth

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
                appointment_id = book(
                    appointment, form_data.get("afspraakOpmerkingen", "")
                )
                result: dict[str, Any] = {
                    "appointment_id": appointment_id,
                    "status": "success",
                }
                submission.save_registration_status(
                    RegistrationStatuses.in_progress, result
                )
            except AppointmentCreateFailed as e:
                logger.error("Appointment creation failed", exc_info=e)
                # This is displayed to the end-user!
                error_information = _(
                    "A technical error occurred while we tried to book your appointment. "
                    "Please verify if all the data is correct or try again later."
                )
                AppointmentInfo.objects.create(
                    status=AppointmentDetailsStatus.failed,
                    error_information=error_information,
                    submission=submission,
                )
                audit_logger.bind(
                    submission_uuid=str(submission.uuid),
                    plugin=appointment_plugin,
                ).warning("appointment_register_failure", exc_info=e)
                raise RegistrationFailed("Unable to create appointment") from e
        else:
            # Reuse existing appointment result
            logger.info("Appointment already created, skipping appointment creation")
            result: dict[str, Any] = {
                "appointment_id": existing_result["appointment_id"],
                "status": existing_result.get("status", "success"),
            }

        return result

    def _get_second_backend(
        self, submission: Submission
    ) -> FormRegistrationBackend | None:
        """Prefer the second configured backend, excluding appointment backends."""
        backends = list(submission.form.registration_backends.all())
        return next(
            (
                backend
                for backend in backends[1:] + backends[:1]
                if backend.backend != PLUGIN_IDENTIFIER
            ),
            None,
        )

    def register_submission(self, submission: Submission, options: dict) -> dict:
        """
        Reuse the booked appointment and register with the second backend.

        The submission processing chain calls this after generating the report.
        """
        result = self.book_appointment(submission)

        if (second_backend := self._get_second_backend(submission)) is not None:
            logger.info(
                "trigger_second_registration_backend", backend=second_backend.backend
            )

            # Get the plugin for the second backend
            second_plugin = register[second_backend.backend]

            # Validate and prepare options
            options_serializer = second_plugin.configuration_options(
                data=second_backend.options,
                context={"validate_business_logic": False},
            )

            if options_serializer.is_valid():
                # Register with the second backend
                try:
                    if not submission.registration_result:
                        submission.registration_result = {}
                    # Set temporary_internal_reference to make sure a kenmerk with OpenFormulieren is added to the StUF-ZDS registration
                    if (
                        "temporary_internal_reference"
                        not in submission.registration_result
                    ):
                        submission.registration_result[
                            "temporary_internal_reference"
                        ] = submission.public_registration_reference
                        submission.save()

                    second_result = second_plugin.register_submission(
                        submission, options_serializer.validated_data
                    )
                    logger.info("second_registration_completed", result=second_result)
                    # Add second registration result to the main result
                    result["second_registration"] = {
                        "backend": second_backend.backend,
                        "result": second_result,
                    }
                except Exception as e:
                    logger.error("second_registration_failed", error=str(e), exc_info=e)
                    # Fail the whole registration if second backend fails
                    result["second_registration"] = {
                        "backend": second_backend.backend,
                        "error": str(e),
                    }
                    raise RegistrationFailed(
                        f"Second registration backend failed: {e}"
                    ) from e
            else:
                logger.error(
                    "second_backend_options_invalid",
                    errors=options_serializer.errors,
                )
                result["second_registration"] = {
                    "backend": second_backend.backend,
                    "error": "Invalid options",
                    "validation_errors": options_serializer.errors,
                }
                raise RegistrationFailed(
                    f"Second registration backend has invalid options: {options_serializer.errors}"
                )

        return result

    @override
    def update_payment_status(self, submission: Submission, options: dict) -> None:
        """Forward payments using the secondary backend's options and result."""
        second_backend = self._get_second_backend(submission)
        if second_backend is None:
            logger.info(
                "appointment_payment_update_skip",
                submission_uuid=str(submission.uuid),
                reason="no_secondary_backend",
            )
            return

        second_plugin = register[second_backend.backend]
        options_serializer = second_plugin.configuration_options(
            data=second_backend.options,
            context={"validate_business_logic": False},
        )
        options_serializer.is_valid(raise_exception=True)

        registration_result = submission.registration_result
        second_registration = (
            registration_result.get("second_registration")
            if registration_result is not None
            else None
        )
        if (
            registration_result is None
            or not isinstance(second_registration, dict)
            or second_registration.get("backend") != second_backend.backend
            or "result" not in second_registration
            or "error" in second_registration
        ):
            raise RegistrationFailed(
                "Secondary registration has not completed successfully"
            )

        second_result = second_registration["result"]
        if second_result is not None and not isinstance(second_result, dict):
            raise RegistrationFailed("Invalid secondary registration result")

        # Secondary plugins expect their result keys at the top level.
        original_result = registration_result.copy()
        try:
            registration_result.update(second_result or {})
            second_plugin.update_payment_status(
                submission, options_serializer.validated_data
            )
        finally:
            registration_result.clear()
            registration_result.update(original_result)

    def check_config(self) -> None:
        # Config checks are not really relevant for this plugin right now
        pass

    @override
    def get_custom_templatetags_libraries(self) -> list[str]:
        prefix = "openforms.registrations.contrib.appointment.templatetags.registrations.contrib"
        return [
            f"{prefix}.appointments.appointment_cancel_link",
        ]


# Keep the concrete plugin type available to the synchronous signal handler.
register(PLUGIN_IDENTIFIER)(AppointmentRegistration)
