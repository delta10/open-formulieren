import traceback

from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

import structlog
from rest_framework.exceptions import ValidationError

from openforms.config.models import GlobalConfiguration
from openforms.logging import logevent
from openforms.submissions.constants import RegistrationStatuses
from openforms.submissions.models import Submission
from openforms.submissions.public_references import set_submission_reference
from openforms.submissions.signals import submission_complete
from openforms.submissions.utils import add_submmission_to_session

from ...exceptions import RegistrationFailed
from .plugin import PLUGIN_IDENTIFIER

logger = structlog.stdlib.get_logger(__name__)


def _appointment_unavailable_validation_error() -> ValidationError:
    return ValidationError(
        {
            "non_field_errors": [
                _(
                    "The selected appointment time is no longer available. "
                    "Please choose a different time slot."
                )
            ]
        }
    )


def _abort_completion(instance: Submission, request, exc: ValidationError) -> None:
    if request is not None:
        add_submmission_to_session(instance, request.session)
    raise exc


@receiver(
    submission_complete,
    dispatch_uid="registrations.appointment.register_submission_sync",
)
def register_appointment_submission(sender, instance: Submission, **kwargs) -> None:
    request = kwargs.get("request")
    backend_config = instance.registration_backend
    if not backend_config or backend_config.backend != PLUGIN_IDENTIFIER:
        return

    registry = backend_config._meta.get_field("backend").registry
    plugin = registry[backend_config.backend]
    log = logger.bind(
        action="registrations.appointment.sync_registration",
        plugin=plugin.identifier,
        submission_uuid=str(instance.uuid),
    )

    if instance.registration_status == RegistrationStatuses.success:
        return

    config = GlobalConfiguration.get_solo()
    if (num_attempts := instance.registration_attempts) >= (
        max_num := config.registration_attempt_limit
    ):
        log.debug(
            "max_registration_attempts_exceeded",
            num_attempts=num_attempts,
            max_num=max_num,
            outcome="abort_completion",
        )
        _abort_completion(
            instance, request, _appointment_unavailable_validation_error()
        )

    if not plugin.is_enabled:
        exc = RegistrationFailed("Registration plugin is not enabled")
        instance.save_registration_status(
            RegistrationStatuses.failed,
            {"traceback": "".join(traceback.format_exception(exc))},
            record_attempt=True,
        )
        logevent.registration_failure(instance, exc, plugin)
        validation_error = ValidationError(
            {"non_field_errors": [_("Registration plugin is not enabled.")]}
        )
        _abort_completion(instance, request, validation_error)

    options_serializer = plugin.configuration_options(
        data=backend_config.options,
        context={"validate_business_logic": False},
    )

    try:
        options_serializer.is_valid(raise_exception=True)
    except ValidationError as exc:
        instance.save_registration_status(
            RegistrationStatuses.failed,
            {"traceback": traceback.format_exc()},
            record_attempt=True,
        )
        logevent.registration_failure(instance, exc, plugin)
        raise

    log.info("registration_start")
    logevent.registration_start(instance)

    instance.last_register_date = timezone.now()
    instance.registration_status = RegistrationStatuses.in_progress
    instance.registration_attempts += 1
    instance.save(
        update_fields=[
            "last_register_date",
            "registration_status",
            "registration_attempts",
        ]
    )

    if not instance.pre_registration_completed:
        set_submission_reference(instance)
        instance.pre_registration_completed = True
        instance.save(
            update_fields=[
                "public_registration_reference",
                "pre_registration_completed",
            ]
        )

    try:
        result = plugin.register_submission(instance, options_serializer.validated_data)
    except RegistrationFailed as exc:
        log.warning("registration_failure", exc_info=exc)
        instance.save_registration_status(
            RegistrationStatuses.failed, {"traceback": traceback.format_exc()}
        )
        logevent.registration_failure(instance, exc, plugin)
        _abort_completion(
            instance, request, _appointment_unavailable_validation_error()
        )
    except Exception as exc:
        log.exception("registration_failure", exc_info=exc)
        instance.save_registration_status(
            RegistrationStatuses.failed, {"traceback": traceback.format_exc()}
        )
        logevent.registration_failure(instance, exc, plugin)
        _abort_completion(
            instance, request, _appointment_unavailable_validation_error()
        )

    log.info("registration_success")
    instance.save_registration_status(RegistrationStatuses.success, result or {})
    logevent.registration_success(instance, plugin)
