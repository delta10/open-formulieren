import traceback
from contextlib import contextmanager

from django.db import transaction
from django.utils import timezone

import structlog
from celery_once import QueueOnce
from glom import assign
from rest_framework.exceptions import ValidationError

from openforms.celery import app
from openforms.config.models import GlobalConfiguration
from openforms.logging import logevent
from openforms.submissions.constants import PostSubmissionEvents, RegistrationStatuses
from openforms.submissions.models import Submission
from openforms.submissions.public_references import set_submission_reference

from .exceptions import RegistrationFailed
from .service import get_registration_plugin

logger = structlog.stdlib.get_logger(__name__)


class ShouldAbort:
    value = False

    def __bool__(self):
        return self.value


@contextmanager
def track_error(submission: Submission, event: PostSubmissionEvents):
    log = logger.bind(submission_uuid=str(submission.uuid), trigger=event)
    should_abort = ShouldAbort()

    try:
        yield should_abort
    except Exception as exc:
        should_abort.value = True

        if not isinstance(exc, ValidationError):
            log.exception("registrations.error", exc_info=exc)

        set_submission_reference(submission)
        submission.save_registration_status(
            RegistrationStatuses.failed,
            {"traceback": traceback.format_exc()},
            record_attempt=True,
        )

        if event == PostSubmissionEvents.on_retry:
            raise exc


@app.task()
def pre_registration(submission_id: int, event: PostSubmissionEvents) -> None:
    submission = Submission.objects.get(id=submission_id)
    log = logger.bind(
        action="registrations.pre_registration",
        submission_uuid=str(submission.uuid),
        trigger=event,
    )
    if not submission.completed_on:
        # This should never happen. Pre-registration shouldn't be attempted for a submission that is not complete.
        log.error("submission_not_completed")
        return

    if submission.pre_registration_completed:
        return

    config = GlobalConfiguration.get_solo()
    if (num_attempts := submission.registration_attempts) >= (
        max_num := config.registration_attempt_limit
    ):
        log.debug(
            "max_registration_attempts_exceeded",
            num_attempts=num_attempts,
            max_num=max_num,
            outcome="skip_pre_registration",
        )
        return

    registration_plugin = get_registration_plugin(submission)
    plugin_repr = (
        None if registration_plugin is None else registration_plugin.identifier
    )
    log = log.bind(plugin=plugin_repr)

    with transaction.atomic():
        if not registration_plugin:
            log.info("generate_submission_reference")
            set_submission_reference(submission)
            structlog.contextvars.bind_contextvars(
                public_reference=submission.public_registration_reference
            )
            submission.pre_registration_completed = True
            submission.save()
            return

        assert submission.registration_backend is not None
        options_serializer = registration_plugin.configuration_options(
            data=submission.registration_backend.options,
            context={"validate_business_logic": False},
        )

        with track_error(submission, event) as should_abort:
            log.debug("validate_registration_plugin_options")
            options_serializer.is_valid(raise_exception=True)

        if should_abort:
            log.debug("abort")
            return

        # If we are retrying, then an internal registration reference has been set. We keep track of it.
        if event == PostSubmissionEvents.on_retry:
            if not submission.registration_result:
                submission.registration_result = {}

            log.debug(
                "store_temporary_internal_reference",
                public_reference=submission.public_registration_reference,
            )
            assign(
                submission.registration_result,
                "temporary_internal_reference",
                submission.public_registration_reference,
                missing=dict,
            )
            submission.save()

    plugin_options = options_serializer.validated_data
    with track_error(submission, event) as should_abort:
        # If an `initial_data_reference` was passed, we must verify that the
        # authenticated user is the owner of the referenced object
        has_initial_data_reference = bool(submission.initial_data_reference)
        log.info("verify_initial_data_ownership", skip=not has_initial_data_reference)
        if has_initial_data_reference:
            # may raise PermissionDenied
            # XXX: audit logging inside this check is likely lost when the outer
            # transaction block rolls back. See
            # https://github.com/open-formulieren/open-forms/pull/4696/files#r1863209778
            registration_plugin.verify_initial_data_ownership(
                submission, plugin_options
            )

        result = registration_plugin.pre_register_submission(submission, plugin_options)

    if should_abort:
        log.debug("abort")
        return

    log.debug("assign_registration_reference")
    if not result.reference:
        set_submission_reference(submission)
    else:
        submission.public_registration_reference = result.reference
    structlog.contextvars.bind_contextvars(
        public_reference=submission.public_registration_reference
    )

    if not submission.registration_result:
        submission.registration_result = {}

    log.debug("clear_error_information")
    if "traceback" in submission.registration_result:
        del submission.registration_result["traceback"]

    if result.data is not None:
        submission.registration_result.update(result.data)

    submission.pre_registration_completed = True
    submission.save()
    log.info("completed")


@app.task(
    base=QueueOnce,
    ignore_result=False,
    once={"graceful": True},  # do not spam error monitoring
)
def register_submission(submission_id: int, event: PostSubmissionEvents | str) -> None:
    """
    Attempt to register the submission with the configured backend.

    Note that there are different triggers that can kick off this task:

    * form submission :func:`openforms.submissions.tasks.on_completion` flow
    * celery beat retry flow
    * admin action to retry the submission

    We should only allow a single registration attempt to run at a given time for a
    given submission. This is achieved through the :class:`QueueOnce` task base class
    from celery-once. While the task is already scheduled, subsequent schedule requests
    will not schedule the task _again_ to celery.

    Submission registration is only executed for "completed" forms, and is delegated
    to the underlying registration backend (if set).
    """
    submission = Submission.objects.select_related("auth_info", "form").get(
        id=submission_id
    )
    form = submission.form
    structlog.contextvars.bind_contextvars(
        form=form.admin_name,
        submission_uuid=str(submission.uuid),
        public_reference=submission.public_registration_reference,
    )
    log = logger.bind(
        action="registrations.main_registration",
        trigger=event,
    )

    if submission.registration_status == RegistrationStatuses.success:
        # if it's already successfully registered, do not overwrite that.
        return

    if not submission.completed_on:
        # This should never happen. Registration shouldn't be attempted for a submission that is not complete.
        log.error("submission_not_completed", outcome="skip")
        return

    if not submission.pre_registration_completed:
        log.debug("pre_registration_not_completed", outcome="skip")
        return

    if submission.cosign_state.is_waiting:
        log.info("skipped_registration", reason="cosign_required", outcome="skip")
        logevent.skipped_registration_cosign_required(submission)
        return

    config = GlobalConfiguration.get_solo()
    if (
        config.wait_for_payment_to_register
        and submission.payment_required
        and not submission.payment_user_has_paid
    ):
        log.info("skipped_registration", reason="payment_not_received", outcome="skip")
        logevent.registration_skipped_not_yet_paid(submission)
        return

    if (num_attempts := submission.registration_attempts) >= (
        max_num := config.registration_attempt_limit
    ):
        # if it fails after this many attempts we give up
        log.debug(
            "max_registration_attempts_exceeded",
            num_attempts=num_attempts,
            max_num=max_num,
            outcome="skip",
        )
        logevent.registration_attempts_limited(submission)
        return

    log.info("registration_start")
    logevent.registration_start(submission)

    submission.last_register_date = timezone.now()
    submission.registration_status = RegistrationStatuses.in_progress
    submission.registration_attempts += 1
    submission.save(
        update_fields=[
            "last_register_date",
            "registration_status",
            "registration_attempts",
        ]
    )

    # figure out which registry and backend to use from the model field used
    backend_config = submission.registration_backend

    if not backend_config or not backend_config.backend:
        log.info("registration_completed", reason="no_registration_plugin_configured")
        submission.save_registration_status(RegistrationStatuses.success, None)
        logevent.registration_skip(submission)
        return

    registry = backend_config._meta.get_field("backend").registry  # pyright: ignore[reportAttributeAccessIssue]
    backend = backend_config.backend

    log.debug("resolve_plugin", plugin_id=backend)
    plugin = registry[backend]
    log = log.bind(plugin=plugin.identifier)

    if not plugin.is_enabled:
        log.info("registration_failure", reason="plugin_disabled")
        exc = RegistrationFailed("Registration plugin is not enabled")
        submission.save_registration_status(
            RegistrationStatuses.failed,
            {"traceback": "".join(traceback.format_exception(exc))},
        )
        logevent.registration_failure(submission, exc)
        if event == PostSubmissionEvents.on_retry:
            raise exc
        return

    log.debug("deserialize_and_validate_registration_plugin_options")
    options_serializer = plugin.configuration_options(
        data=backend_config.options,
        context={"validate_business_logic": False},
    )

    try:
        options_serializer.is_valid(raise_exception=True)
    except ValidationError as exc:
        logevent.registration_failure(submission, exc, plugin)
        log.warning("registration_failure", reason="invalid_options", exc_info=exc)
        submission.save_registration_status(
            RegistrationStatuses.failed, {"traceback": traceback.format_exc()}
        )
        if event == PostSubmissionEvents.on_retry:
            raise exc
        return

    log.debug("call_plugin")
    try:
        result = plugin.register_submission(
            submission, options_serializer.validated_data
        )
    except RegistrationFailed as exc:
        log.warning("registration_failure", exc_info=exc)
        submission.save_registration_status(
            RegistrationStatuses.failed, {"traceback": traceback.format_exc()}
        )
        logevent.registration_failure(submission, exc, plugin)
        if event == PostSubmissionEvents.on_retry:
            raise exc
        return
    except Exception as exc:
        log.exception("registration_failure", exc_info=exc)
        submission.save_registration_status(
            RegistrationStatuses.failed, {"traceback": traceback.format_exc()}
        )
        logevent.registration_failure(submission, exc, plugin)
        if event == PostSubmissionEvents.on_retry:
            raise exc
        return

    log.info("registration_success")
    if (
        config.wait_for_payment_to_register
        and event == PostSubmissionEvents.on_payment_complete
    ):
        submission.payments.mark_registered()
        log.info("marked_payments_registered")

    submission.save_registration_status(RegistrationStatuses.success, result or {})
    logevent.registration_success(submission, plugin)
    log.info("done")


def update_registration_with_confirmation_email(submission_id: int) -> None:
    log = logger.bind(
        action="registrations.update_registration_with_confirmation_email"
    )

    submission = Submission.objects.get(id=submission_id)

    if submission.registration_status != RegistrationStatuses.success:
        log.info(
            "update_registration_with_confirmation_email_aborted",
            reason="main_registration_not_successful",
        )
        return

    plugin = get_registration_plugin(submission)
    if plugin is None:
        log.info(
            "update_registration_with_confirmation_email_completed",
            reason="no_plugin_is_configured",
        )
        logevent.registration_update_with_confirmation_email_skip(submission)
        return

    if not plugin.is_enabled:
        log.info(
            "update_registration_with_confirmation_email_failed",
            reason="plugin_is_disabled",
        )
        exc = RegistrationFailed("Registration plugin is not enabled")
        logevent.registration_update_with_confirmation_email_failure(
            submission, exc, plugin
        )
        return

    assert submission.registration_backend is not None
    options_serializer = plugin.configuration_options(
        data=submission.registration_backend.options,
        context={"validate_business_logic": False},
    )

    try:
        options_serializer.is_valid(raise_exception=True)
    except ValidationError as exc:
        log.warning(
            "update_registration_with_confirmation_email_failed",
            reason="invalid_options",
            exc_info=exc,
        )
        logevent.registration_update_with_confirmation_email_failure(
            submission, exc, plugin
        )
        return

    assert submission.registration_result is not None
    try:
        result = plugin.update_registration_with_confirmation_email(
            submission, options_serializer.validated_data
        )
    except (RegistrationFailed, Exception) as exc:
        log.warning("update_registration_with_confirmation_email_failed", exc_info=exc)
        submission.registration_result["update_with_confirmation_emails_traceback"] = (
            traceback.format_exc()
        )
        submission.save(update_fields=["registration_result"])
        logevent.registration_update_with_confirmation_email_failure(
            submission, exc, plugin
        )
        return

    if result:
        submission.registration_result.update(result)
    submission.save(update_fields=["registration_result"])
    logevent.registration_update_with_confirmation_email_success(submission, plugin)
    log.info("done")
