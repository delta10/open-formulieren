from django.test import tag

import requests_mock
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory, APITestCase
from zgw_consumers.test.factories import ServiceFactory

from openforms.accounts.tests.factories import SuperUserFactory
from openforms.forms.tests.factories import (
    FormFactory,
    FormLogicFactory,
    FormStepFactory,
    FormVariableFactory,
)
from openforms.variables.tests.factories import ServiceFetchConfigurationFactory

from ...api.viewsets import SubmissionStepViewSet
from ..factories import SubmissionFactory, SubmissionStepFactory
from ..mixins import SubmissionsMixin


class CheckLogicEndpointTests(SubmissionsMixin, APITestCase):
    maxDiff = None

    def test_update_not_applicable_steps(self):
        form = FormFactory.create()
        step1 = FormStepFactory.create(
            form=form,
            form_definition__configuration={
                "components": [
                    {
                        "type": "select",
                        "key": "pet",
                        "data": {
                            "values": [
                                {"label": "Cat", "value": "cat"},
                                {"label": "Dog", "value": "dog"},
                            ]
                        },
                    }
                ]
            },
        )
        step2 = FormStepFactory.create(
            form=form,
            form_definition__configuration={
                "components": [
                    {
                        "type": "textfield",
                        "key": "step2",
                    }
                ]
            },
        )
        step3 = FormStepFactory.create(
            form=form,
            form_definition__configuration={
                "components": [
                    {
                        "type": "textfield",
                        "key": "step3",
                    }
                ]
            },
        )
        FormLogicFactory.create(
            form=form,
            json_logic_trigger={
                "==": [
                    {"var": "pet"},
                    "cat",
                ]
            },
            actions=[
                {
                    "form_step_uuid": f"{step2.uuid}",
                    "action": {
                        "name": "Step is not applicable",
                        "type": "step-not-applicable",
                    },
                }
            ],
        )
        FormLogicFactory.create(
            form=form,
            json_logic_trigger={
                "==": [
                    {"var": "pet"},
                    "dog",
                ]
            },
            actions=[
                {
                    "form_step_uuid": f"{step3.uuid}",
                    "action": {
                        "name": "Step is not applicable",
                        "type": "step-not-applicable",
                    },
                }
            ],
        )
        submission = SubmissionFactory.create(form=form)

        SubmissionStepFactory.create(
            submission=submission,
            form_step=step1,
            data={"pet": "dog"},  # With this data, step 3 is not applicable
        )

        endpoint = reverse(
            "api:submission-steps-logic-check",
            kwargs={"submission_uuid": submission.uuid, "step_uuid": step1.uuid},
        )
        self._add_submission_to_session(submission)

        # Make a change to the data, which causes step 2 to be not applicable (while step 3 is applicable again)
        response = self.client.post(endpoint, data={"data": {"pet": "cat"}})

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertFalse(response.data["submission"]["steps"][1]["is_applicable"])
        self.assertTrue(response.data["submission"]["steps"][2]["is_applicable"])

    def test_endpoint_loads_submission_with_auth_info(self):
        submission = SubmissionFactory.create()
        submission_step = SubmissionStepFactory.create(submission=submission)

        request = APIRequestFactory().get("/")
        request.user = SuperUserFactory.create()

        def check_object_permissions(request, submission_step):
            return True

        endpoint = SubmissionStepViewSet()
        endpoint.kwargs = dict(
            submission_uuid=submission.uuid, step_uuid=submission_step.form_step.uuid
        )
        endpoint.request = request
        endpoint.check_object_permissions = check_object_permissions

        object = endpoint.get_object()

        # Check that get_object retrieves also the auth info as part of the select related
        with self.assertNumQueries(0):
            hasattr(object.submission, "auth_info")

    def test_updating_data_marks_step_as_applicable_again(self):
        form = FormFactory.create()
        form_step0 = FormStepFactory.create(form=form)
        form_step1 = FormStepFactory.create(
            form=form,
            form_definition__configuration={
                "components": [
                    {
                        "type": "radio",
                        "key": "radio",
                        "values": [
                            {"label": "A", "value": "a"},
                            {"label": "B", "value": "b"},
                        ],
                    }
                ]
            },
        )
        form_step2 = FormStepFactory.create(form=form)
        FormLogicFactory.create(
            form=form,
            json_logic_trigger={
                "==": [
                    {"var": "radio"},
                    "a",
                ]
            },
            actions=[
                {
                    "form_step_uuid": f"{form_step2.uuid}",
                    "action": {
                        "name": "Step is not applicable",
                        "type": "step-not-applicable",
                    },
                }
            ],
        )
        submission = SubmissionFactory.create(form=form)
        SubmissionStepFactory.create(
            submission=submission, form_step=form_step0, data={"some": "data"}
        )
        SubmissionStepFactory.create(
            submission=submission,
            form_step=form_step1,
            data={"radio": "a"},
        )

        endpoint = reverse(
            "api:submission-steps-logic-check",
            kwargs={"submission_uuid": submission.uuid, "step_uuid": form_step1.uuid},
        )
        self._add_submission_to_session(submission)

        # Make a change to the data, which causes step 2 to be applicable again
        response = self.client.post(endpoint, data={"data": {"radio": "b"}})

        data = response.json()

        self.assertTrue(data["submission"]["steps"][2]["isApplicable"])

    @tag("gh-3647")
    def test_sending_invalid_time_values(self):
        submission = SubmissionFactory.from_components(
            components_list=[
                {"type": "time", "key": "time"},
                {"type": "date", "key": "date"},
                {"type": "datetime", "key": "datetime"},
            ]
        )

        endpoint = reverse(
            "api:submission-steps-logic-check",
            kwargs={
                "submission_uuid": submission.uuid,
                "step_uuid": submission.submissionstep_set.first().form_step.uuid,
            },
        )
        self._add_submission_to_session(submission)

        with self.subTest("Invalid time with good format"):
            response = self.client.post(endpoint, data={"data": {"time": "25:00"}})

            self.assertEqual(response.status_code, status.HTTP_200_OK)

        with self.subTest("Invalid time with bad format"):
            response = self.client.post(endpoint, data={"data": {"time": "Invalid"}})

            self.assertEqual(response.status_code, status.HTTP_200_OK)

        with self.subTest("Invalid date"):
            response = self.client.post(endpoint, data={"data": {"date": "2020-13-46"}})

            self.assertEqual(response.status_code, status.HTTP_200_OK)

        with self.subTest("Invalid datetime"):
            response = self.client.post(
                endpoint, data={"data": {"datetime": "2022-13-46T00:00:00+02:00"}}
            )

            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_handling_none_values_in_logic(self):
        submission = SubmissionFactory.from_components(
            components_list=[
                {"type": "time", "key": "time"},
                {"type": "date", "key": "date"},
                {"type": "datetime", "key": "datetime"},
                {"type": "textfield", "key": "result"},
                {"type": "date", "key": "resultDate"},
                {"type": "datetime", "key": "resultDatetime"},
            ]
        )
        FormLogicFactory.create(
            form=submission.form,
            json_logic_trigger={
                "and": [
                    {"==": [None, {"var": "time"}]},
                    {"==": [None, {"var": "date"}]},
                    {"==": [None, {"var": "datetime"}]},
                ]
            },
            actions=[
                {
                    "variable": "result",
                    "action": {
                        "type": "variable",
                        "value": "All the variables were None",
                    },
                }
            ],
        )
        FormLogicFactory.create(
            form=submission.form,
            json_logic_trigger=True,
            actions=[
                {
                    "variable": "resultDate",
                    "action": {
                        "type": "variable",
                        "value": {"+": [{"var": "date"}, {"duration": "P1M"}]},
                    },
                },
                {
                    "variable": "resultDatetime",
                    "action": {
                        "type": "variable",
                        "value": {"+": [{"var": "datetime"}, {"duration": "P1M"}]},
                    },
                },
            ],
        )
        endpoint = reverse(
            "api:submission-steps-logic-check",
            kwargs={
                "submission_uuid": submission.uuid,
                "step_uuid": submission.submissionstep_set.first().form_step.uuid,
            },
        )
        self._add_submission_to_session(submission)

        response = self.client.post(
            endpoint,
            data={
                "data": {
                    "time": "Invalid",
                    "date": "2020-13-46",
                    "datetime": "2022-13-46T00:00:00+02:00",
                }
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()

        self.assertEqual(data["step"]["data"]["result"], "All the variables were None")
        for key in ("time", "date", "datetime", "resultDate", "resultDatetime"):
            self.assertNotIn(key, data["step"]["data"])

    @tag("gh-3975")
    @requests_mock.Mocker()
    def test_old_service_fetch_config_ignored(self, m):
        form = FormFactory.create()
        step = FormStepFactory.create(
            form=form,
            form_definition__configuration={
                "components": [
                    {
                        "type": "textfield",
                        "key": "someComponent",
                    }
                ]
            },
        )
        service = ServiceFactory.create(
            api_root="https://httpbin.org/",
        )
        m.get("https://httpbin.org/get", json={"oh": "some data"})
        FormVariableFactory.create(
            form=form,
            key="aVariable",
            service_fetch_configuration=ServiceFetchConfigurationFactory.create(
                service=service,
                path="get",
            ),
        )
        FormLogicFactory.create(
            form=form,
            json_logic_trigger={"!!": [True]},
            actions=[
                {
                    "action": {
                        "type": "fetch-from-service",
                        "value": "4000",
                    },  # A non-existing service
                    "variable": "aVariable",
                    "component": "",
                    "form_step": "",
                    "form_step_uuid": None,
                }
            ],
        )
        submission = SubmissionFactory.create(form=form)

        endpoint = reverse(
            "api:submission-steps-logic-check",
            kwargs={"submission_uuid": submission.uuid, "step_uuid": step.uuid},
        )
        self._add_submission_to_session(submission)

        response = self.client.post(endpoint, data={"data": {}})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_only_changed_data_is_returned_after_submitting_step(self):
        submission = SubmissionFactory.from_components(
            [{"key": "textfield", "type": "textfield", "label": "Textfield"}]
        )

        endpoint = reverse(
            "api:submission-steps-logic-check",
            kwargs={
                "submission_uuid": submission.uuid,
                "step_uuid": submission.form.formstep_set.first().uuid,
            },
        )
        self._add_submission_to_session(submission)

        response = self.client.post(endpoint, data={"data": {"textfield": "foo"}})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["step"]["data"], {})

        # Simulate submitting the step (this creates the submission value variables)
        submission_step = submission.submissionstep_set.first()
        submission_step.data = {"textfield": "foo"}

        # Ensure returned data is still empty after moving back to the submitted step
        response = self.client.post(endpoint, data={"data": {"textfield": "bar"}})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # No changes during logic evaluation, so the returned data should be empty
        self.assertEqual(response.json()["step"]["data"], {})

    def test_clear_on_hide_behaviour(self):
        """
        Test clear-on-hide behaviour in two ways:
          1. Components that are shown by default and get hidden when a logic rule
             triggers
          2. Components that are hidden by default and get shown when a logic rule
             triggers (key contains "Inverted"). This means they become hidden again
             when a logic rule DOESN'T trigger.
        """
        submission = SubmissionFactory.from_components(
            [
                {
                    "key": "checkbox",
                    "type": "checkbox",
                    "label": "Checkbox",
                },
                {
                    "key": "textfield",
                    "type": "textfield",
                    "label": "Textfield",
                    "clearOnHide": True,
                    "hidden": False,
                },
                {
                    "key": "textfieldInverted",
                    "type": "textfield",
                    "label": "Textfield Inverted",
                    "clearOnHide": True,
                    "hidden": True,
                },
                {
                    "key": "date",
                    "type": "date",
                    "label": "Date",
                    "clearOnHide": True,
                    "hidden": False,
                },
                {
                    "key": "dateInverted",
                    "type": "date",
                    "label": "Date Inverted",
                    "clearOnHide": True,
                    "hidden": True,
                },
                {
                    "key": "fieldset",
                    "type": "fieldset",
                    "label": "Fieldset",
                    "clearOnHide": True,
                    "hidden": False,
                    "components": [
                        {
                            "type": "textfield",
                            "key": "textfieldInFieldset",
                            "label": "Textfield in Fieldset",
                            "clearOnHide": True,
                        },
                        {
                            "type": "textfield",
                            "key": "textfieldInFieldsetWithoutClearOnHide",
                            "label": "Textfield in Fieldset w/o clearOnHide",
                            "clearOnHide": False,
                        },
                    ],
                },
                {
                    "key": "fieldsetInverted",
                    "type": "fieldset",
                    "label": "FieldsetInverted",
                    "clearOnHide": True,
                    "hidden": True,
                    "components": [
                        {
                            "type": "textfield",
                            "key": "textfieldInInvertedFieldset",
                            "label": "Textfield in inverted Fieldset",
                            "clearOnHide": True,
                        },
                        {
                            "type": "textfield",
                            "key": "textfieldInInvertedFieldsetWithoutClearOnHide",
                            "label": "Textfield in inverted Fieldset w/o clearOnHide",
                            "clearOnHide": False,
                        },
                    ],
                },
                {
                    "key": "editgrid",
                    "type": "editgrid",
                    "label": "Editgrid",
                    "clearOnHide": True,
                    "hidden": False,
                    "components": [
                        {
                            "type": "textfield",
                            "key": "textfieldInEditgrid",
                            "label": "Textfield in Editgrid",
                            "clearOnHide": True,
                        },
                    ],
                },
                {
                    "key": "editgridInverted",
                    "type": "editgrid",
                    "label": "Editgrid inverted",
                    "clearOnHide": True,
                    "hidden": True,
                    "components": [
                        {
                            "type": "textfield",
                            "key": "textfieldInInvertedEditgrid",
                            "label": "Textfield in inverted Editgrid",
                            "clearOnHide": True,
                        },
                    ],
                },
            ]
        )

        FormLogicFactory.create(
            form=submission.form,
            json_logic_trigger={"==": [{"var": "checkbox"}, True]},
            actions=[
                {
                    "component": key,
                    "action": {
                        "name": "Hide element",
                        "type": "property",
                        "property": {"value": "hidden", "type": "bool"},
                        "state": state,
                    },
                }
                for key, state in [
                    ("textfield", True),
                    ("textfieldInverted", False),
                    ("date", True),
                    ("dateInverted", False),
                    ("fieldset", True),
                    ("fieldsetInverted", False),
                    ("editgrid", True),
                    ("editgridInverted", False),
                ]
            ],
        )

        endpoint = reverse(
            "api:submission-steps-logic-check",
            kwargs={
                "submission_uuid": submission.uuid,
                "step_uuid": submission.form.formstep_set.first().uuid,
            },
        )
        self._add_submission_to_session(submission)

        with self.subTest("Logic rule is triggered"):
            # Assuming we go from an unchecked to a checked state for the checkbox, all
            # components with ``"hidden": False`` will be visible initially
            response = self.client.post(
                endpoint,
                data={
                    "data": {
                        "checkbox": True,
                        "textfield": "a",
                        "date": "2025-08-27",
                        "textfieldInFieldset": "b",
                        "textfieldInFieldsetWithoutClearOnHide": "c",
                        "editgrid": [
                            {"textfieldInEditgrid": "d"},
                            {"textfieldInEditgrid": "e"},
                        ],
                    },
                },
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(
                response.json()["step"]["data"],
                {
                    "textfield": "",
                    "date": "",
                    "textfieldInFieldset": "",
                    "editgrid": [],
                },
            )

        with self.subTest("Logic rule is not triggered"):
            # Assuming we go from a checked to an unchecked state for the checkbox, all
            # components with ``"hidden": True`` will be visible initially
            response = self.client.post(
                endpoint,
                data={
                    "data": {
                        "checkbox": False,
                        "textfieldInverted": "a",
                        "dateInverted": "2025-08-27",
                        "textfieldInInvertedFieldset": "b",
                        "textfieldInInvertedFieldsetWithoutClearOnHide": "c",
                        "editgridInverted": [
                            {"textfieldInInvertedEditgrid": "d"},
                            {"textfieldInInvertedEditgrid": "e"},
                        ],
                    },
                },
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(
                response.json()["step"]["data"],
                {
                    "textfieldInverted": "",
                    "dateInverted": "",
                    "textfieldInInvertedFieldset": "",
                    "editgridInverted": [],
                },
            )

    def test_clear_on_hide_behaviour_with_multiple_steps(self):
        """
        Ensure that logic check only returns cleared values relevant for the current
        step.
        """
        form = FormFactory.create()
        step_1 = FormStepFactory.create(
            form=form,
            form_definition__configuration={
                "components": [
                    {
                        "type": "checkbox",
                        "key": "checkbox",
                        "label": "Show all textfields",
                    },
                    {
                        "type": "textfield",
                        "key": "textfieldStep1",
                        "hidden": True,
                        "clearOnHide": True,
                    },
                ]
            },
        )
        step_2 = FormStepFactory.create(
            form=form,
            form_definition__configuration={
                "components": [
                    {
                        "type": "textfield",
                        "key": "textfieldStep2",
                        "hidden": True,
                        "clearOnHide": True,
                    }
                ]
            },
        )

        submission = SubmissionFactory.create(form=form)
        # We assume the user has already gone through both of the steps, entered some
        # data, and returned to the first step
        submission_step_1 = SubmissionStepFactory.create(
            submission=submission,
            form_step=step_1,
            data={"checkbox": True, "textfieldStep1": "some data"},
        )
        SubmissionStepFactory.create(
            submission=submission,
            form_step=step_2,
            data={"textfieldStep2": "some data"},
        )

        FormLogicFactory.create(
            form=submission.form,
            json_logic_trigger={"==": [{"var": "checkbox"}, True]},
            actions=[
                {
                    "component": "textfieldStep1",
                    "action": {
                        "name": "Hide element",
                        "type": "property",
                        "property": {"value": "hidden", "type": "bool"},
                        "state": False,
                    },
                },
                {
                    "component": "textfieldStep2",
                    "action": {
                        "name": "Hide element",
                        "type": "property",
                        "property": {"value": "hidden", "type": "bool"},
                        "state": False,
                    },
                },
            ],
        )

        with self.subTest("logic in step 2"):
            endpoint = reverse(
                "api:submission-steps-logic-check",
                kwargs={
                    "submission_uuid": submission.uuid,
                    "step_uuid": step_1.uuid,
                },
            )
            self._add_submission_to_session(submission)
            response = self.client.post(
                endpoint,
                data={
                    "data": {
                        "checkbox": False,
                        "textfieldStep1": "some data",
                    },
                },
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            # Ensure that we only receive cleared data for the first step
            self.assertEqual(
                response.json()["step"]["data"],
                {"textfieldStep1": ""},
            )

        # Simulate navigating to the next step
        submission_step_1.data = {"checkbox": False, "textfieldStep1": ""}

        with self.subTest("logic in step 2"):
            endpoint = reverse(
                "api:submission-steps-logic-check",
                kwargs={
                    "submission_uuid": submission.uuid,
                    "step_uuid": step_2.uuid,
                },
            )
            self._add_submission_to_session(submission)
            response = self.client.post(
                endpoint,
                data={
                    "data": {"textfieldStep2": "some data"},
                },
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            # Ensure that we only receive cleared data for the second step
            self.assertEqual(
                response.json()["step"]["data"],
                {"textfieldStep2": ""},
            )
