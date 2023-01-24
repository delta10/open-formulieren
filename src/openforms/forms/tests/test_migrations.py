from rest_framework.reverse import reverse

from openforms.utils.tests.test_migrations import TestMigrations

CONFIGURATION = {
    "components": [
        {"type": "textfield", "key": "test1"},
        {
            "type": "fieldset",
            "key": "test2",
            "components": [],
            "logic": [
                {
                    "name": "Rule 1",
                    "trigger": {
                        "type": "javascript",  # Not supported, will be skipped
                        "javascript": "result = data['test'];",
                    },
                    "actions": [
                        {
                            "name": "Rule 1 Action 1",
                            "type": "property",
                            "property": {
                                "label": "Hidden",
                                "value": "hidden",
                                "type": "boolean",
                            },
                            "state": True,
                        }
                    ],
                },
                {
                    "name": "Rule 2",
                    "trigger": {
                        "type": "simple",
                        "simple": {
                            "show": True,
                            "when": "test1",
                            "eq": "trigger value",
                        },
                    },
                    "actions": [
                        {
                            "name": "Rule 2 Action 1",
                            "type": "property",
                            "property": {
                                "label": "Hidden",
                                "value": "hidden",
                                "type": "boolean",
                            },
                            "state": False,
                        }
                    ],
                },
                {
                    "name": "Rule 3",
                    "trigger": {
                        "type": "json",
                        "json": {"==": [{"var": "test1"}, "test"]},
                    },
                    "actions": [
                        {
                            "name": "Rule 3 Action 1",
                            "type": "property",
                            "property": {
                                "label": "Required",
                                "value": "validate.required",
                                "type": "boolean",
                            },
                            "state": True,
                        },
                        {
                            "name": "Rule 3 Action 2",
                            "type": "property",
                            "property": {
                                "label": "Disabled",
                                "value": "disabled",
                                "type": "boolean",
                            },
                            "state": True,
                        },
                        {
                            "name": "Rule 3 Action 3",
                            "type": "property",
                            "property": {
                                "label": "Title",
                                "value": "title",  # Not supported, will be skipped
                                "type": "string",
                            },
                            "text": "A new title",
                        },
                    ],
                },
            ],
        },
    ]
}


class TestChangeInlineEditSetting(TestMigrations):
    migrate_from = "0058_formdefinition_component_translations"
    migrate_to = "0059_editgrid_inline_false"
    app = "forms"

    def setUpBeforeMigration(self, apps):
        FormDefinition = apps.get_model("forms", "FormDefinition")
        self.form_definition = FormDefinition.objects.create(
            name="Definition with repeating group",
            slug="definition-with-repeating-group",
            configuration={
                "components": [
                    {
                        "key": "repeatingGroup",
                        "type": "editgrid",
                        "label": "Repeating Group",
                        "inlineEdit": True,
                        "components": [],
                    }
                ]
            },
        )

    def test_inline_edit_is_true(self):
        self.form_definition.refresh_from_db()

        self.assertFalse(
            self.form_definition.configuration["components"][0]["inlineEdit"]
        )


class TestUpdateTranslationFields(TestMigrations):
    migrate_from = "0050_auto_20221024_1252"
    migrate_to = "0051_update_translation_fields"
    app = "forms"

    def setUpBeforeMigration(self, apps):
        FormDefinition = apps.get_model("forms", "FormDefinition")
        self.form_definition = FormDefinition.objects.create(
            name="Vertaalbare naam",
            configuration={
                "components": [
                    {
                        "key": "repeatingGroup",
                        "type": "editgrid",
                        "label": "Repeating Group",
                        "inlineEdit": False,
                        "components": [],
                    }
                ]
            },
        )

    def test_update_translation_fields(self):
        self.form_definition.refresh_from_db()

        self.assertEqual(self.form_definition.name, "Vertaalbare naam")
        self.assertEqual(self.form_definition.name_nl, "Vertaalbare naam")
        self.assertEqual(self.form_definition.name_en, None)


class TestConvertURLsToUUIDs(TestMigrations):
    migrate_from = "0050_alter_formvariable_key"
    migrate_to = "0051_replace_urls_with_uuids"
    app = "forms"

    def setUpBeforeMigration(self, apps):
        Form = apps.get_model("forms", "Form")
        FormDefinition = apps.get_model("forms", "FormDefinition")
        FormStep = apps.get_model("forms", "FormStep")
        FormLogic = apps.get_model("forms", "FormLogic")

        form = Form.objects.create(name="Form", slug="form")
        form_definition = FormDefinition.objects.create(
            name="Vertaalbare naam",
            configuration={
                "components": [
                    {
                        "key": "test",
                        "type": "textfield",
                    }
                ]
            },
        )
        form_step = FormStep.objects.create(
            form=form, form_definition=form_definition, order=0
        )

        form_step_path = reverse(
            "api:form-steps-detail",
            kwargs={"form_uuid_or_slug": form.uuid, "uuid": form_step.uuid},
        )

        self.rule = FormLogic.objects.create(
            form=form,
            order=1,
            json_logic_trigger={"==": [{"var": "test"}, "test"]},
            actions=[
                {
                    "form_step": f"http://example.com{form_step_path}",
                    "action": {
                        "name": "Step is not applicable",
                        "type": "step-not-applicable",
                    },
                }
            ],
        )
        self.form_step = form_step

    def test_assert_url_converted_correctly(self):
        self.rule.refresh_from_db()

        self.assertEqual(
            self.rule.actions[0]["form_step_uuid"], str(self.form_step.uuid)
        )


class TestChangeHideLabelSetting(TestMigrations):
    migrate_from = "0054_merge_20221114_1308"
    migrate_to = "0055_make_hidelabel_false"
    app = "forms"

    def setUpBeforeMigration(self, apps):
        FormDefinition = apps.get_model("forms", "FormDefinition")
        self.form_definition = FormDefinition.objects.create(
            name="Definition with repeating group",
            slug="definition-with-repeating-group",
            configuration={
                "components": [
                    {
                        "key": "repeatingGroup",
                        "type": "editgrid",
                        "label": "Repeating Group",
                        "hideLabel": True,
                        "components": [],
                    },
                    {
                        "key": "SomeTextField",
                        "type": "textfield",
                        "label": "Text Field",
                        "hideLabel": True,
                    },
                ]
            },
        )

    def test_editgrid_hidelabel_false(self):
        self.form_definition.refresh_from_db()

        self.assertFalse(
            self.form_definition.configuration["components"][0]["hideLabel"]
        )
        self.assertTrue(
            self.form_definition.configuration["components"][1]["hideLabel"]
        )


class GenerateLogicDescriptions(TestMigrations):
    app = "forms"
    migrate_from = "0060_formlogic_description"
    migrate_to = "0061_generate_logic_rule_descriptions"

    def setUpBeforeMigration(self, apps):
        FormDefinition = apps.get_model("forms", "FormDefinition")
        Form = apps.get_model("forms", "Form")
        FormLogic = apps.get_model("forms", "FormLogic")
        FormStep = apps.get_model("forms", "FormStep")

        form = Form.objects.create(slug="form")
        form_def = FormDefinition.objects.create(
            slug="form_def",
            configuration={
                "components": [
                    {
                        "type": "textfield",
                        "key": "textfield",
                    },
                    {
                        "type": "editgrid",
                        "key": "items",
                        "components": [
                            {
                                "type": "textfield",
                                "key": "name",
                            },
                        ],
                    },
                ]
            },
        )
        FormStep.objects.create(form=form, form_definition=form_def, order=0)
        # simple rule
        fl1 = FormLogic.objects.create(
            form=form,
            order=0,
            json_logic_trigger={"!=": [{"var": "textfield"}, "foo"]},
            actions=[
                {
                    "action": {
                        "type": "property",
                        "state": False,
                        "property": {"type": "bool", "value": "hidden"},
                    },
                    "component": "items",
                }
            ],
        )
        self.fl1_pk = fl1.pk
        # complex rule
        fl2 = FormLogic.objects.create(
            form=form,
            order=1,
            json_logic_trigger={
                ">": [
                    {
                        "reduce": [
                            {"var": "items"},
                            {"+": [{"var": "accumulator"}, 1]},
                            0,
                        ]
                    },
                    1,
                ]
            },
            actions=[
                {
                    "action": {
                        "type": "property",
                        "state": False,
                        "property": {"type": "bool", "value": "hidden"},
                    },
                    "component": "textfield",
                }
            ],
        )
        self.fl2_pk = fl2.pk

    def test_description_filled_simple_rule(self):
        FormLogic = self.apps.get_model("forms", "FormLogic")
        instance = FormLogic.objects.get(pk=self.fl1_pk)

        self.assertNotEqual(instance.description, "")

    def test_description_filled_complex_rule(self):
        FormLogic = self.apps.get_model("forms", "FormLogic")
        instance = FormLogic.objects.get(pk=self.fl2_pk)

        self.assertNotEqual(instance.description, "")


class TestAddRadioType(TestMigrations):
    migrate_from = "0064_auto_20230113_1641"
    migrate_to = "0065_set_radio_data_type"
    app = "forms"

    def setUpBeforeMigration(self, apps):
        FormDefinition = apps.get_model("forms", "FormDefinition")
        self.form_definition = FormDefinition.objects.create(
            name="Definition with radio",
            slug="definition-with-radio",
            configuration={
                "components": [
                    {
                        "key": "someRadioString",
                        "type": "radio",
                        "label": "Radiooo Striiing",
                    },
                    {
                        "key": "someRadioInt",
                        "type": "radio",
                        "label": "Radiooo Iiint",
                        "dataType": "int",
                    },
                    {
                        "key": "SomeTextField",
                        "type": "textfield",
                        "label": "Text Field",
                    },
                ]
            },
        )

    def test_radio_has_datatype(self):
        self.form_definition.refresh_from_db()

        self.assertEqual(
            self.form_definition.configuration["components"][0]["dataType"], "string"
        )
        self.assertEqual(
            self.form_definition.configuration["components"][1]["dataType"], "int"
        )
        self.assertNotIn(
            "dataType", self.form_definition.configuration["components"][2]
        )


class TestFixTypo(TestMigrations):
    migrate_from = "0066_merge_20230119_1618"
    migrate_to = "0067_fix_typo_20230124_1624"
    app = "forms"

    def setUpBeforeMigration(self, apps):
        FormDefinition = apps.get_model("forms", "FormDefinition")
        self.form_definition = FormDefinition.objects.create(
            name="Definition with typo",
            slug="definition-with-typo",
            configuration={
                "components": [
                    {
                        "key": "someString",
                        "registration": {"attribute": "Strainitiator_straatat"},
                    },
                ]
            },
        )

    def test_typo_is_fixed(self):
        self.form_definition.refresh_from_db()

        self.assertEqual(
            self.form_definition.configuration["components"][0]["registration"][
                "attribute"
            ],
            "initiator_straat",
        )
