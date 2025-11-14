from unittest.mock import patch

from django.test import override_settings

from privates.test import temp_private_root
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from openforms.appointments.constants import AppointmentDetailsStatus
from openforms.appointments.models import AppointmentInfo, AppointmentsConfig
from openforms.config.models import GlobalConfiguration
from openforms.forms.tests.factories import FormRegistrationBackendFactory
from openforms.payments.constants import PaymentStatus
from openforms.payments.services import update_submission_payment_registration
from openforms.payments.tests.factories import SubmissionPaymentFactory
from openforms.registrations.contrib.appointment.plugin import AppointmentRegistration
from openforms.registrations.exceptions import RegistrationFailed
from openforms.registrations.tasks import register_submission
from openforms.submissions.constants import (
    SUBMISSIONS_SESSION_KEY,
    PostSubmissionEvents,
    RegistrationStatuses,
)
from openforms.submissions.tests.factories import (
    SubmissionFactory,
    SubmissionReportFactory,
)
from openforms.submissions.tests.mixins import SubmissionsMixin


class AppointmentRegistrationBackendTests(APITestCase):
    def test_secondary_registration_never_selects_appointment(self):
        register = AppointmentRegistration.register_submission
        for backends, selected_plugin in (
            (("appointment", "demo"), "DemoRegistration"),
            (("demo", "appointment"), "DemoRegistration"),
            (("demo", "failing-demo", "appointment"), "DemoFailRegistration"),
        ):
            with self.subTest(backends=backends):
                submission = SubmissionFactory.create(completed=True)
                for backend in backends:
                    configuration = FormRegistrationBackendFactory.create(
                        form=submission.form, backend=backend, options={}
                    )
                    if backend == "appointment":
                        submission.finalised_registration_backend_key = (
                            configuration.key
                        )
                submission.save()
                with (
                    patch.object(
                        AppointmentRegistration,
                        "book_appointment",
                        return_value={"appointment_id": "appointment-123"},
                    ) as mock_book,
                    patch.object(
                        AppointmentRegistration,
                        "register_submission",
                        side_effect=RegistrationFailed(
                            "Recursive appointment registration"
                        ),
                    ) as mock_recursive,
                    patch(
                        f"openforms.registrations.contrib.demo.plugin.{selected_plugin}.register_submission",
                        return_value={"reference": "case-123"},
                    ) as mock_secondary,
                ):
                    result = register(
                        AppointmentRegistration("appointment"), submission, {}
                    )

                mock_recursive.assert_not_called()
                mock_book.assert_called_once()
                mock_secondary.assert_called_once()
                self.assertEqual(result["appointment_id"], "appointment-123")
                self.assertEqual(
                    result["second_registration"]["result"], {"reference": "case-123"}
                )

    def test_payment_update_uses_secondary_result_and_can_retry(self):
        for backends in (
            ("appointment", "stuf-zds-create-zaak"),
            ("stuf-zds-create-zaak", "appointment"),
        ):
            with self.subTest(backends=backends):
                registration_result = {
                    "appointment_id": "appointment-123",
                    "second_registration": {
                        "backend": "stuf-zds-create-zaak",
                        "result": {"zaak": "case-123", "document": "document-123"},
                    },
                }
                submission = SubmissionFactory.create(
                    with_public_registration_reference=True,
                    registration_result=registration_result,
                )
                for backend in backends:
                    configuration = FormRegistrationBackendFactory.create(
                        form=submission.form,
                        backend=backend,
                        options={}
                        if backend == "appointment"
                        else {
                            "zds_omschrijving": "",
                            "zds_toelichting": "",
                            "zds_zaaktype_code": "appointment-case",
                            "zds_uitvoerende_afdeling": "",
                            "zds_documenttype_omschrijving_inzending": "",
                        },
                    )
                    if backend == "appointment":
                        submission.finalised_registration_backend_key = (
                            configuration.key
                        )
                submission.save()
                payment = SubmissionPaymentFactory.create(
                    submission=submission, status=PaymentStatus.completed
                )

                with patch(
                    "openforms.registrations.contrib.stuf_zds.plugin.get_client"
                ) as mock_get_client:
                    client = mock_get_client.return_value.__enter__.return_value
                    client.set_zaak_payment.side_effect = [
                        RegistrationFailed("Service unavailable"),
                        None,
                    ]

                    with self.assertRaisesMessage(
                        RegistrationFailed, "Service unavailable"
                    ):
                        update_submission_payment_registration(submission)

                    self.assertEqual(
                        submission.registration_result, registration_result
                    )
                    payment.refresh_from_db()
                    self.assertEqual(payment.status, PaymentStatus.completed)

                    update_submission_payment_registration(submission)

                self.assertEqual(client.set_zaak_payment.call_count, 2)
                self.assertEqual(client.set_zaak_payment.call_args.args[0], "case-123")
                self.assertEqual(
                    mock_get_client.call_args.args[0]["zds_zaaktype_code"],
                    "appointment-case",
                )
                self.assertEqual(submission.registration_result, registration_result)
                submission.refresh_from_db()
                self.assertEqual(submission.registration_result, registration_result)
                payment.refresh_from_db()
                self.assertEqual(payment.status, PaymentStatus.registered)

    @patch(
        "openforms.registrations.contrib.email.plugin.EmailRegistration.update_payment_status"
    )
    def test_payment_update_rejects_invalid_secondary_options(self, mock_update):
        submission = SubmissionFactory.create(
            with_public_registration_reference=True,
            registration_result={
                "appointment_id": "appointment-123",
                "second_registration": {"backend": "email", "result": None},
            },
        )
        FormRegistrationBackendFactory.create(
            form=submission.form, backend="appointment", options={}
        )
        FormRegistrationBackendFactory.create(
            form=submission.form, backend="email", options={}
        )
        payment = SubmissionPaymentFactory.create(
            submission=submission, status=PaymentStatus.completed
        )

        with self.assertRaises(ValidationError):
            update_submission_payment_registration(submission)

        mock_update.assert_not_called()
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.completed)

    @patch(
        "openforms.registrations.contrib.email.plugin.EmailRegistration.update_payment_status"
    )
    def test_payment_update_requires_successful_secondary_registration(
        self, mock_update
    ):
        for receipt, succeeds in (
            (None, False),
            ({"backend": "demo", "result": None}, False),
            ({"backend": "email", "error": "Registration failed"}, False),
            ({"backend": "email", "result": "invalid"}, False),
            ({"backend": "email", "result": None}, True),
        ):
            with self.subTest(receipt=receipt):
                submission = SubmissionFactory.create(
                    with_public_registration_reference=True,
                    registration_result={
                        "appointment_id": "appointment-123",
                        "second_registration": receipt,
                    },
                )
                FormRegistrationBackendFactory.create(
                    form=submission.form, backend="appointment", options={}
                )
                FormRegistrationBackendFactory.create(
                    form=submission.form,
                    backend="email",
                    options={"to_emails": ["test@example.com"]},
                )
                payment = SubmissionPaymentFactory.create(
                    submission=submission, status=PaymentStatus.completed
                )
                mock_update.reset_mock()

                if succeeds:
                    update_submission_payment_registration(submission)
                    mock_update.assert_called_once()
                    self.assertEqual(
                        mock_update.call_args.args[1]["to_emails"], ["test@example.com"]
                    )
                else:
                    with self.assertRaises(RegistrationFailed):
                        update_submission_payment_registration(submission)
                    mock_update.assert_not_called()

                payment.refresh_from_db()
                self.assertEqual(
                    payment.status,
                    PaymentStatus.registered if succeeds else PaymentStatus.completed,
                )


@temp_private_root()
class AppointmentRegistrationCompletionTests(SubmissionsMixin, APITestCase):
    @patch("openforms.submissions.api.mixins.on_post_submission_event")
    @patch(
        "openforms.appointments.contrib.demo.plugin.DemoAppointment.create_appointment",
        return_value="appointment-123",
    )
    @patch(
        "openforms.registrations.contrib.demo.plugin.DemoRegistration.register_submission",
        side_effect=[
            RegistrationFailed("Backend unavailable"),
            {"reference": "case-123"},
        ],
    )
    def test_second_backend_retry_preserves_booked_appointment(
        self,
        mock_second_backend,
        mock_create_appointment,
        mock_on_post_submission_event,
    ):
        AppointmentsConfig.objects.create(plugin="demo")
        config = GlobalConfiguration.get_solo()
        config.registration_attempt_limit = 2
        config.save()
        form_data = {
            "afspraakDatum": "2030-12-01",
            "afspraakTijd": "12:00",
            "afspraakBranchId": "location-1",
            "afspraakServiceId": "product-1",
        }
        submission = SubmissionFactory.from_components(
            [{"key": key, "type": "textfield"} for key in form_data],
            submitted_data=form_data,
            with_report=False,
        )
        self.assertFalse(submission.form.is_appointment)
        FormRegistrationBackendFactory.create(
            form=submission.form, backend="appointment", options={}
        )
        FormRegistrationBackendFactory.create(
            form=submission.form, backend="demo", options={}
        )
        self._add_submission_to_session(submission)
        endpoint = reverse("api:submission-complete", kwargs={"uuid": submission.uuid})

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(endpoint, {"privacy_policy_accepted": True})

        mock_create_appointment.assert_called_once()
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
        mock_second_backend.assert_not_called()
        mock_on_post_submission_event.assert_called_once_with(
            submission.id, PostSubmissionEvents.on_completion
        )
        submission.refresh_from_db()
        self.assertTrue(submission.is_completed)
        self.assertEqual(
            submission.registration_status, RegistrationStatuses.in_progress
        )
        self.assertEqual(
            submission.registration_result["appointment_id"], "appointment-123"
        )
        info = AppointmentInfo.objects.get(submission=submission)

        SubmissionReportFactory.create(submission=submission)
        register_submission.run(submission.id, PostSubmissionEvents.on_completion)

        submission.refresh_from_db()
        self.assertEqual(submission.registration_status, RegistrationStatuses.failed)
        self.assertEqual(
            submission.registration_result["appointment_id"], "appointment-123"
        )
        info.refresh_from_db()
        self.assertEqual(info.status, AppointmentDetailsStatus.success)

        register_submission.run(submission.id, PostSubmissionEvents.on_retry)
        register_submission.run(submission.id, PostSubmissionEvents.on_retry)

        submission.refresh_from_db()
        self.assertEqual(submission.registration_status, RegistrationStatuses.success)
        self.assertEqual(
            submission.registration_result["second_registration"],
            {"backend": "demo", "result": {"reference": "case-123"}},
        )
        self.assertEqual(mock_second_backend.call_count, 2)
        mock_create_appointment.assert_called_once()
        info.refresh_from_db()
        self.assertEqual(info.appointment_id, "appointment-123")

    @patch("openforms.submissions.api.mixins.on_post_submission_event")
    @patch(
        "openforms.registrations.contrib.appointment.plugin.AppointmentRegistration.book_appointment",
        return_value={"appointment_id": "appointment-123", "status": "success"},
    )
    def test_appointment_booking_runs_synchronously(
        self, mock_book_appointment, mock_on_post_submission_event
    ):
        config = GlobalConfiguration.get_solo()
        config.registration_attempt_limit = 1
        config.save()
        submission = SubmissionFactory.from_components(
            [{"key": "foo", "type": "textfield"}], submitted_data={"foo": "bar"}
        )
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
        mock_book_appointment.assert_called_once()
        mock_on_post_submission_event.assert_called_once_with(
            submission.id, PostSubmissionEvents.on_completion
        )

        submission.refresh_from_db()
        self.assertTrue(submission.is_completed)
        self.assertTrue(submission.pre_registration_completed)
        self.assertEqual(
            submission.registration_status, RegistrationStatuses.in_progress
        )
        self.assertEqual(
            submission.registration_result,
            {"appointment_id": "appointment-123", "status": "success"},
        )

        register_submission.run(submission.id, PostSubmissionEvents.on_completion)

        submission.refresh_from_db()
        self.assertEqual(submission.registration_status, RegistrationStatuses.success)

    @override_settings(LANGUAGE_CODE="en")
    @patch("openforms.submissions.api.mixins.on_post_submission_event")
    @patch(
        "openforms.registrations.contrib.appointment.plugin.AppointmentRegistration.book_appointment",
        side_effect=[
            RegistrationFailed("Unable to create appointment"),
            {"appointment_id": "appointment-123", "status": "success"},
        ],
    )
    def test_appointment_registration_backend_failure_keeps_submission_active(
        self, mock_book_appointment, mock_on_post_submission_event
    ):
        submission = SubmissionFactory.from_components(
            [{"key": "foo", "type": "textfield"}], submitted_data={"foo": "bar"}
        )
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
        mock_book_appointment.assert_called_once()
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
        self.assertEqual(mock_book_appointment.call_count, 2)
        mock_on_post_submission_event.assert_called_once_with(
            submission.id, PostSubmissionEvents.on_completion
        )

        submission.refresh_from_db()
        self.assertTrue(submission.is_completed)
        self.assertEqual(
            submission.registration_status, RegistrationStatuses.in_progress
        )

    @override_settings(LANGUAGE_CODE="nl")
    @patch("openforms.submissions.api.mixins.on_post_submission_event")
    @patch(
        "openforms.registrations.contrib.appointment.plugin.AppointmentRegistration.book_appointment",
        side_effect=RegistrationFailed("Unable to create appointment"),
    )
    def test_appointment_registration_backend_failure_is_translated(
        self, mock_book_appointment, mock_on_post_submission_event
    ):
        submission = SubmissionFactory.from_components(
            [{"key": "foo", "type": "textfield"}], submitted_data={"foo": "bar"}
        )
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
        mock_book_appointment.assert_called_once()
        mock_on_post_submission_event.assert_not_called()
