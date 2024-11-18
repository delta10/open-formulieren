from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from hypothesis import given
from hypothesis.extra.django import TestCase as HypothesisTestCase

from openforms.accounts.tests.factories import UserFactory
from openforms.config.models.config import GlobalConfiguration
from openforms.forms.api.datastructures import FormVariableWrapper
from openforms.forms.api.serializers import FormSerializer
from openforms.forms.api.serializers.logic.action_serializers import (
    LogicComponentActionSerializer,
)
from openforms.forms.tests.factories import (
    FormFactory,
    FormRegistrationBackendFactory,
    FormStepFactory,
    FormVariableFactory,
)
from openforms.registrations.base import BasePlugin as BaseRegistrationPlugin
from openforms.registrations.registry import Registry as RegistrationPluginRegistry
from openforms.tests.search_strategies import json_primitives
from openforms.variables.constants import FormVariableDataTypes, FormVariableSources


class LogicComponentActionSerializerPropertyTest(HypothesisTestCase):
    @given(json_primitives())
    def test_date_format_validation_against_primitive_json_values(self, json_value):
        """Assert that serializer is invalid for random Primitive json data types
        (str, int, etc.) as logic action values for date variables
        """
        form = FormFactory.create()
        FormVariableFactory.create(
            source=FormVariableSources.user_defined,
            key="date_var",
            form=form,
            data_type=FormVariableDataTypes.date,
        )
        form_vars = FormVariableWrapper(form=form)

        serializer = LogicComponentActionSerializer(
            data={
                "variable": "date_var",
                "action": {
                    "type": "variable",
                    "value": json_value,
                },
            },
            context={"request": None, "form_variables": form_vars},
        )
        self.assertFalse(serializer.is_valid())


class LogicComponentActionSerializerTest(TestCase):
    def test_date_variable_with_non_trivial_json_trigger(self):
        """Check that valid JSON expressions are not ruled out by date format validation"""
        form = FormFactory.create()
        FormVariableFactory.create(
            source=FormVariableSources.user_defined,
            key="someDate",
            form=form,
            data_type=FormVariableDataTypes.date,
        )
        FormVariableFactory.create(
            source=FormVariableSources.user_defined,
            key="anotherDate",
            form=form,
            data_type=FormVariableDataTypes.date,
        )
        form_vars = FormVariableWrapper(form=form)

        serializer = LogicComponentActionSerializer(
            data={
                "json_logic_trigger": {
                    "==": [
                        {"var": "someDate"},
                        {},
                    ]
                },
                "variable": "anotherDate",
                "action": {
                    "type": "variable",
                    "value": {"var": "anotherDate"},
                },
            },
            context={"request": None, "form_variables": form_vars},
        )

        self.assertTrue(serializer.is_valid())

    def test_registration_backend_action_errors_no_value(self):
        form = FormFactory.create()
        context = {"request": None, "form_variables": FormVariableWrapper(form=form)}

        serializer = LogicComponentActionSerializer(
            data={
                "json_logic_trigger": False,
                "action": {
                    "type": "set-registration-backend",
                },
            },
            context=context,
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["action"]["value"][0].code, "required")

    def test_invalid_action(self):
        form = FormFactory.create()
        context = {"request": None, "form_variables": FormVariableWrapper(form=form)}

        serializer = LogicComponentActionSerializer(
            data={
                "json_logic_trigger": False,
                "action": {
                    "type": "does-not-exist",
                },
            },
            context=context,
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["action"]["type"][0].code, "invalid_choice")


class FormSerializerTest(TestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(GlobalConfiguration.clear_cache)

    def test_form_with_cosign(self):
        form_step = FormStepFactory.create(
            form__slug="form-with-cosign",
            form__authentication_backends=["digid"],
            form_definition__configuration={
                "components": [
                    {
                        "key": "cosignField",
                        "label": "Cosign",
                        "type": "cosign",
                    }
                ]
            },
        )

        factory = RequestFactory()
        request = factory.get("/foo")
        request.user = UserFactory.create()

        serializer = FormSerializer(
            instance=form_step.form, context={"request": request}
        )
        cosign_login_options = serializer.data["cosign_login_options"]
        cosign_login_info = serializer.data["cosign_login_info"]

        self.assertEqual(len(cosign_login_options), 1)
        self.assertEqual(cosign_login_options[0]["identifier"], "digid")
        self.assertIsNotNone(cosign_login_info)
        self.assertEqual(cosign_login_info["identifier"], "digid")

    @patch(
        "openforms.forms.api.serializers.form.GlobalConfiguration.get_solo",
        return_value=GlobalConfiguration(
            cosign_request_template="{{ form_name }} cosign request."
        ),
    )
    def test_form_without_cosign_link_used_in_email(self, mock_get_solo):
        form_step = FormStepFactory.create(
            form__slug="form-with-cosign",
            form__authentication_backends=["digid"],
            form_definition__configuration={
                "components": [
                    {
                        "key": "cosignField",
                        "label": "Cosign",
                        "type": "cosign",
                    }
                ]
            },
        )
        factory = RequestFactory()
        request = factory.get("/foo")
        request.user = AnonymousUser()

        serializer = FormSerializer(
            instance=form_step.form, context={"request": request}
        )

        cosign_login_options = serializer.data["cosign_login_options"]
        self.assertEqual(len(cosign_login_options), 1)
        self.assertFalse(serializer.data["cosign_has_link_in_email"])

    @patch(
        "openforms.forms.api.serializers.form.GlobalConfiguration.get_solo",
        return_value=GlobalConfiguration(
            cosign_request_template="{{ form_url }} cosign request."
        ),
    )
    def test_form_with_cosign_link_used_in_email(self, mock_get_solo):
        form_step = FormStepFactory.create(
            form__slug="form-with-cosign",
            form__authentication_backends=["digid"],
            form_definition__configuration={
                "components": [
                    {
                        "key": "cosignField",
                        "label": "Cosign",
                        "type": "cosign",
                    }
                ]
            },
        )
        factory = RequestFactory()
        request = factory.get("/foo")
        request.user = AnonymousUser()

        serializer = FormSerializer(
            instance=form_step.form, context={"request": request}
        )

        cosign_login_options = serializer.data["cosign_login_options"]
        self.assertEqual(len(cosign_login_options), 1)
        self.assertTrue(serializer.data["cosign_has_link_in_email"])

    def test_form_without_cosign(self):
        form_step = FormStepFactory.create(
            form__slug="form-without-cosign",
            form__authentication_backends=["digid"],
            form_definition__configuration={
                "components": [
                    {
                        "key": "notCosign",
                        "label": "Not Cosign",
                        "type": "textfield",
                    }
                ]
            },
        )

        factory = RequestFactory()
        request = factory.get("/foo")
        request.user = UserFactory.create()

        serializer = FormSerializer(
            instance=form_step.form, context={"request": request}
        )
        cosign_login_options = serializer.data["cosign_login_options"]
        cosign_login_info = serializer.data["cosign_login_info"]

        self.assertEqual(cosign_login_options, [])
        self.assertIsNone(cosign_login_info)

    def test_patching_registrations_deleting_the_first(self):
        form = FormFactory.create()
        FormRegistrationBackendFactory.create(
            form=form,
            key="backend1",
            name="#1",
            backend="email",
            options={"to_emails": ["you@example.com"]},
        )
        FormRegistrationBackendFactory.create(
            form=form,
            key="backend2",
            name="#2",
            backend="email",
            options={"to_emails": ["me@example.com"]},
        )
        context = {"request": None}
        data = FormSerializer(context=context).to_representation(form)
        # remove v2 data
        del data["registration_backend"]
        del data["registration_backend_options"]

        # delete the first line
        assert data["registration_backends"][0]["key"] == "backend1"
        del data["registration_backends"][0]

        serializer = FormSerializer(instance=form, context=context, data=data)
        self.assertTrue(serializer.is_valid())
        serializer.save()
        form.refresh_from_db()

        self.assertEqual(form.registration_backends.count(), 1)
        backend = form.registration_backends.first()
        self.assertEqual(backend.key, "backend2")
        self.assertEqual(backend.name, "#2")
        self.assertEqual(backend.backend, "email")
        self.assertEqual(backend.options["to_emails"], ["me@example.com"])

    def test_patching_registrations_with_a_booboo(self):
        form = FormFactory.create()
        FormRegistrationBackendFactory.create(
            form=form,
            key="backend1",
            name="#1",
            backend="email",
            options={"to_emails": ["you@example.com"]},
        )
        FormRegistrationBackendFactory.create(
            form=form,
            key="backend2",
            name="#2",
            backend="email",
            options={"to_emails": ["me@example.com"]},
        )
        context = {"request": None}
        data = FormSerializer(context=context).to_representation(form)

        all_the_same = 3 * [
            {
                "key": "backend5",
                "name": "#5",
                "backend": "email",
                "options": {"to_emails": ["booboo@example.com", "yogi@example.com"]},
            }
        ]

        data["registration_backends"] = all_the_same

        serializer = FormSerializer(instance=form, context=context, data=data)
        with self.assertRaises(Exception):
            self.assertTrue(serializer.is_valid())
            serializer.save()

        form.refresh_from_db()

        # assert no changes made
        self.assertEqual(form.registration_backends.count(), 2)
        backend1, backend2 = form.registration_backends.all()
        self.assertEqual(backend1.key, "backend1")
        self.assertEqual(backend1.name, "#1")
        self.assertEqual(backend1.backend, "email")
        self.assertEqual(backend1.options["to_emails"], ["you@example.com"])
        self.assertEqual(backend2.key, "backend2")
        self.assertEqual(backend2.name, "#2")
        self.assertEqual(backend2.backend, "email")
        self.assertEqual(backend2.options["to_emails"], ["me@example.com"])

    def test_patching_registration_passing_none_options(self):
        # deprecated case
        context = {"request": None}
        data = FormSerializer(context=context).to_representation(
            instance=FormFactory.create(slug="unicorn-slug")
        )
        # not a v3 call
        del data["registration_backends"]
        # options v2 are nullable
        data["registration_backend"] = "nullable-unicorn"
        data["registration_backend_options"] = None
        data["slug"] = "another-slug"

        mock_register = RegistrationPluginRegistry()

        @mock_register("nullable-unicorn")
        class UnicornPlugin(BaseRegistrationPlugin):
            # This doesn't pass registry.check_plugin
            # configuration_options = None

            def register_submission(self, *args, **kwargs):
                pass

        # this
        # UnicornPlugin.configuration_options.allow_null = True
        # still raises in FormSerializer.validate_backend_options:
        # ValidationError({'non_field_errors': [ErrorDetail(string='No data provided', code='null')]})

        # In theory, a 3rd party could do
        UnicornPlugin.configuration_options = None

        with patch(f"{FormSerializer.__module__}.registration_register", mock_register):
            serializer = FormSerializer(context=context, data=data)
            self.assertTrue(serializer.is_valid())
            form = serializer.save()

        backends = list(form.registration_backends.all())
        self.assertEqual(len(backends), 1)
        self.assertEqual(backends[0].backend, "nullable-unicorn")
        self.assertFalse(backends[0].options)

    def test_patching_registrations_backend(self):
        # testing v2 patching
        form = FormFactory.create()
        FormRegistrationBackendFactory.create(form=form, backend="demo-failing")
        context = {"request": None}

        serializer = FormSerializer(
            instance=form,
            context=context,
            data={"registration_backend": "demo"},
            partial=True,
        )
        self.assertTrue(serializer.is_valid())
        serializer.save()
        form.refresh_from_db()

        self.assertEqual(form.registration_backends.count(), 1)
        backend = form.registration_backends.first()
        self.assertEqual(backend.backend, "demo")

    def test_patching_registrations_backend_with_new_instance(self):
        # testing v2 patching
        form = FormFactory.create()
        context = {"request": None}

        serializer = FormSerializer(
            instance=form,
            context=context,
            data={"registration_backend": "demo", "registration_backend_options": {}},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(raise_exception=True))
        serializer.save()
        form.refresh_from_db()

        self.assertEqual(form.registration_backends.count(), 1)
        backend = form.registration_backends.first()
        self.assertEqual(backend.backend, "demo")
