import uuid
from unittest.mock import patch

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from openforms.submissions.models import Submission
from openforms.submissions.tests.factories import SubmissionFactory
from openforms.submissions.tests.mixins import SubmissionsMixin

from ...constants import AuthAttribute
from ...registry import Registry
from ...tests.test_registry import Plugin


class LogoutTest(SubmissionsMixin, APITestCase):
    def test_logout(self):
        register = Registry()

        register("plugin1")(Plugin)
        plugin1 = register["plugin1"]
        plugin1.provides_auth = AuthAttribute.bsn

        register("plugin2")(Plugin)
        plugin2 = register["plugin2"]
        plugin2.provides_auth = AuthAttribute.kvk

        session = self.client.session
        session[AuthAttribute.bsn] = "123456789"
        session[AuthAttribute.kvk] = "987654321"
        session[AuthAttribute.pseudo] = "99999999"
        session.save()

        self.assertIn(AuthAttribute.bsn, self.client.session)
        self.assertIn(AuthAttribute.kvk, self.client.session)

        with patch("openforms.authentication.views.register", register):
            response = self.client.delete(reverse("api:logout"))

        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertNotIn(AuthAttribute.bsn, self.client.session)
        self.assertNotIn(AuthAttribute.kvk, self.client.session)
        self.assertNotIn(AuthAttribute.pseudo, self.client.session)

    def test_submissions_in_session_auth_attributes_hashed(self):
        submission = SubmissionFactory.create(completed=False, bsn="000000000")
        self._add_submission_to_session(submission)

        response = self.client.delete(reverse("api:logout"))

        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        submission.refresh_from_db()
        self.assertNotEqual(submission.bsn, "")
        # check that the submission is hashed
        self.assertNotEqual(submission.bsn, "000000000")


class SubmissionLogoutTest(SubmissionsMixin, APITestCase):
    def test_logout_requires_submission_in_session(self):
        with self.subTest("fails when submission does not exist"):
            url = reverse("api:submission-logout", kwargs={"uuid": uuid.uuid4()})
            response = self.client.delete(url)
            self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

        submission = SubmissionFactory.create(completed=False, bsn="000000000")
        url = reverse("api:submission-logout", kwargs={"uuid": submission.uuid})

        with self.subTest("fails when submission not in session"):
            response = self.client.delete(url)
            self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

        with self.subTest("success when submission in session"):
            # now add it
            self._add_submission_to_session(submission)
            response = self.client.delete(url)
            self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

    def test_logout(self):
        submission = SubmissionFactory.create(completed=False, bsn="000000000")
        url = reverse("api:submission-logout", kwargs={"uuid": submission.uuid})

        self._add_submission_to_session(submission)

        # call the endpoint
        response = self.client.delete(url)

        # not actually deleted
        self.assertTrue(Submission.objects.filter(uuid=submission.uuid).exists())

        self.assertNotIn(str(submission.uuid), self._get_session_submission_uuids())

        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertNotIn(AuthAttribute.bsn, self.client.session)
        self.assertNotIn(AuthAttribute.kvk, self.client.session)
        self.assertNotIn(AuthAttribute.pseudo, self.client.session)
