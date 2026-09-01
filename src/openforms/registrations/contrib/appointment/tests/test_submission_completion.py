from unittest.mock import patch

from django.test import override_settings

from privates.test import temp_private_root
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from openforms.forms.tests.factories import FormRegistrationBackendFactory
from openforms.registrations.exceptions import RegistrationFailed
from openforms.submissions.constants import (
    SUBMISSIONS_SESSION_KEY,
    PostSubmissionEvents,
    RegistrationStatuses,
)
from openforms.submissions.tests.factories import SubmissionFactory
from openforms.submissions.tests.mixins import SubmissionsMixin


@temp_private_root()
class AppointmentRegistrationCompletionTests(SubmissionsMixin, APITestCase):
    @patch("openforms.submissions.api.mixins.on_post_submission_event")
    @patch(
        "openforms.registrations.contrib.appointment.plugin.AppointmentRegistration.register_submission",
        return_value={"appointment_id": "appointment-123", "status": "success"},
    )
    def test_appointment_registration_backend_runs_synchronously(
        self, mock_register_submission, mock_on_post_submission_event
    ):
        submission = SubmissionFactory.from_data({"foo": "bar"})
        FormRegistrationBackendFactory.create(
            form=submission.form,
            backend="appointment",
            options={},
        )
        self._add_submission_to_session(submission)
        endpoint = reverse("api:submission-complete", kwargs={"uuid": submission.uuid})

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(endpoint, {"privacy_policy_accepted": True})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_register_submission.assert_called_once()
        mock_on_post_submission_event.assert_called_once_with(
            submission.id, PostSubmissionEvents.on_completion
        )

        submission.refresh_from_db()
        self.assertTrue(submission.is_completed)
        self.assertTrue(submission.pre_registration_completed)
        self.assertEqual(submission.registration_status, RegistrationStatuses.success)
        self.assertEqual(
            submission.registration_result,
            {"appointment_id": "appointment-123", "status": "success"},
        )

    @override_settings(LANGUAGE_CODE="en")
    @patch("openforms.submissions.api.mixins.on_post_submission_event")
    @patch(
        "openforms.registrations.contrib.appointment.plugin.AppointmentRegistration.register_submission",
        side_effect=[
            RegistrationFailed("Unable to create appointment"),
            {"appointment_id": "appointment-123", "status": "success"},
        ],
    )
    def test_appointment_registration_backend_failure_keeps_submission_active(
        self, mock_register_submission, mock_on_post_submission_event
    ):
        submission = SubmissionFactory.from_data({"foo": "bar"})
        FormRegistrationBackendFactory.create(
            form=submission.form,
            backend="appointment",
            options={},
        )
        self._add_submission_to_session(submission)
        endpoint = reverse("api:submission-complete", kwargs={"uuid": submission.uuid})

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(endpoint, {"privacy_policy_accepted": True})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["code"], "invalid")
        self.assertEqual(
            response.json()["invalidParams"],
            [
                {
                    "name": "nonFieldErrors",
                    "code": "invalid",
                    "reason": "The selected appointment time is no longer available. Please choose a different time slot.",
                }
            ],
        )
        mock_register_submission.assert_called_once()
        mock_on_post_submission_event.assert_not_called()

        submission.refresh_from_db()
        self.assertFalse(submission.is_completed)
        self.assertEqual(submission.registration_status, RegistrationStatuses.pending)
        self.assertIn(
            str(submission.uuid),
            response.wsgi_request.session[SUBMISSIONS_SESSION_KEY],
        )

        with self.captureOnCommitCallbacks(execute=True):
            second_response = self.client.post(
                endpoint, {"privacy_policy_accepted": True}
            )

        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_register_submission.call_count, 2)
        mock_on_post_submission_event.assert_called_once_with(
            submission.id, PostSubmissionEvents.on_completion
        )

        submission.refresh_from_db()
        self.assertTrue(submission.is_completed)
        self.assertEqual(submission.registration_status, RegistrationStatuses.success)

    @override_settings(LANGUAGE_CODE="nl")
    @patch("openforms.submissions.api.mixins.on_post_submission_event")
    @patch(
        "openforms.registrations.contrib.appointment.plugin.AppointmentRegistration.register_submission",
        side_effect=RegistrationFailed("Unable to create appointment"),
    )
    def test_appointment_registration_backend_failure_is_translated(
        self, mock_register_submission, mock_on_post_submission_event
    ):
        submission = SubmissionFactory.from_data({"foo": "bar"})
        FormRegistrationBackendFactory.create(
            form=submission.form,
            backend="appointment",
            options={},
        )
        self._add_submission_to_session(submission)
        endpoint = reverse("api:submission-complete", kwargs={"uuid": submission.uuid})

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(endpoint, {"privacy_policy_accepted": True})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json()["invalidParams"][0]["reason"],
            "Het gekozen afspraaktijdstip is niet meer beschikbaar. Kies een ander tijdstip.",
        )
        mock_register_submission.assert_called_once()
        mock_on_post_submission_event.assert_not_called()
