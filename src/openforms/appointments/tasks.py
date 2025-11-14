import structlog
from celery_once import QueueOnce

from openforms.celery import app
from openforms.submissions.models import Submission

from .core import book_for_submission
from .exceptions import AppointmentRegistrationFailed, NoAppointmentForm

__all__ = ["maybe_register_appointment"]

logger = structlog.stdlib.get_logger(__name__)


def _uses_appointment_registration_backend(submission: Submission) -> bool:
    backend_config = submission.registration_backend
    return bool(backend_config and backend_config.backend == "appointment")


@app.task(
    base=QueueOnce,
    ignore_result=False,
    once={"graceful": True},  # do not spam error monitoring
)
def maybe_register_appointment(submission_id: int) -> None | str:
    """
    Register an appointment for the submission IF relevant.

    If the submission is for a form which is configured to create appointments,
    ensure that the appointment is registered in the configured backend.

    This can either be successful or fail. Either way, the result should
    be stored in the database. If appointment registration fails, this feedback
    should find its way back to the end-user.
    """
    submission = Submission.objects.select_related("form").get(id=submission_id)
    log = logger.bind(submission_uuid=str(submission.uuid))
    log.info("appointment_registration")

    if _uses_appointment_registration_backend(submission):
        log.info(
            "appointment_registration_skip",
            reason="appointment_registration_backend_handles_booking",
        )
        return None

    try:
        return book_for_submission(submission=submission)
    except NoAppointmentForm:
        pass
    except AppointmentRegistrationFailed as exc:
        log.info("appointment_registration_failure", exc_info=exc)
        raise
