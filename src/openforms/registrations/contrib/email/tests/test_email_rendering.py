from unittest.mock import patch

from django.test import RequestFactory, TestCase

from openforms.submissions.tests.factories import SubmissionFactory

from ..models import EmailConfig
from ..utils import get_registration_email_templates
from ..views import EmailRegistrationTestView


class RenderRegistrationEmailTests(TestCase):
    def test_preview_uses_backend_templates(self):
        submission = SubmissionFactory.create(
            form__registration_backend="email",
            form__registration_backend_options={
                "to_emails": ["test@test.nl"],
                "email_content_template_html": "<p>Custom HTML template</p>",
                "email_content_template_text": "Custom text template",
            },
        )

        for mode, expected in (
            ("html", "<p>Custom HTML template</p>"),
            ("text", "Custom text template\n"),
        ):
            with self.subTest(mode=mode):
                view = EmailRegistrationTestView()
                view.setup(RequestFactory().get("/", {"mode": mode}))
                view.object = submission

                self.assertEqual(view.get_email_content(), expected)

    def test_preview_without_backend_uses_global_templates(self):
        submission = SubmissionFactory.create()

        with patch(
            "openforms.registrations.contrib.email.plugin.EmailConfig.get_solo",
            return_value=EmailConfig(
                content_html="<p>Global HTML template</p>",
                content_text="Global text template",
            ),
        ):
            for mode, expected in (
                ("html", "<p>Global HTML template</p>"),
                ("text", "Global text template\n"),
            ):
                with self.subTest(mode=mode):
                    view = EmailRegistrationTestView()
                    view.setup(RequestFactory().get("/", {"mode": mode}))
                    view.object = submission

                    self.assertEqual(view.get_email_content(), expected)

    def test_only_global_template_used(self):
        submission = SubmissionFactory.create(
            form__registration_backend="email",
            form__registration_backend_options={
                "to_emails": ["test@test.nl"],
            },
        )

        with patch(
            "openforms.registrations.contrib.email.utils.EmailConfig.get_solo",
            return_value=EmailConfig(
                subject="Global Subject",
                payment_subject="Global Payment Subject",
                content_html="Global HTML template",
                content_text="Global text template",
            ),
        ):
            templates = get_registration_email_templates(submission)

        self.assertEqual(templates.subject, "Global Subject")
        self.assertEqual(templates.payment_subject, "Global Payment Subject")
        self.assertEqual(templates.content_html, "Global HTML template")
        self.assertEqual(templates.content_text, "Global text template")

    def test_can_overwrite_just_subject(self):
        submission = SubmissionFactory.create(
            form__registration_backend="email",
            form__registration_backend_options={
                "to_emails": ["test@test.nl"],
                "email_subject": "Custom subject",
            },
        )

        with patch(
            "openforms.registrations.contrib.email.utils.EmailConfig.get_solo",
            return_value=EmailConfig(
                subject="Global Subject",
                payment_subject="Global Payment Subject",
                content_html="Global HTML template",
                content_text="Global text template",
            ),
        ):
            templates = get_registration_email_templates(submission)

        self.assertEqual(templates.subject, "Custom subject")
        self.assertEqual(templates.payment_subject, "Global Payment Subject")
        self.assertEqual(templates.content_html, "Global HTML template")
        self.assertEqual(templates.content_text, "Global text template")

    def test_can_overwrite_all_templates(self):
        submission = SubmissionFactory.create(
            form__registration_backend="email",
            form__registration_backend_options={
                "to_emails": ["test@test.nl"],
                "email_subject": "Custom subject",
                "email_payment_subject": "Custom Payment Subject",
                "email_content_template_html": "Custom HTML template",
                "email_content_template_text": "Custom text template",
            },
        )

        with patch(
            "openforms.registrations.contrib.email.utils.EmailConfig.get_solo",
            return_value=EmailConfig(
                subject="Global Subject",
                payment_subject="Global Payment Subject",
                content_html="Global HTML template",
                content_text="Global text template",
            ),
        ):
            templates = get_registration_email_templates(submission)

        self.assertEqual(templates.subject, "Custom subject")
        self.assertEqual(templates.payment_subject, "Custom Payment Subject")
        self.assertEqual(templates.content_html, "Custom HTML template")
        self.assertEqual(templates.content_text, "Custom text template")
