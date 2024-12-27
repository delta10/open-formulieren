# Generated by Django 4.2.17 on 2024-12-27 14:35

import re
from decimal import Decimal

import django.core.validators
from django.db import migrations, models
from django.db.migrations.state import StateApps

import tinymce.models

import csp_post_processor.fields
from openforms.forms.constants import LogicActionTypes
from openforms.forms.migration_operations import ConvertComponentsOperation
from openforms.variables.constants import FormVariableDataTypes, FormVariableSources

VARIABLE_NAME = "Total price"
VARIABLE_KEY = "totalPrice"


def _assignment_action(key: str, value: Decimal):
    return {
        "variable": key,
        "action": {
            "type": LogicActionTypes.variable,
            "value": str(value),
        },
    }


def convert_price_logic_rules_to_price_variable(apps: StateApps, _):
    """
    For each form that has price logic rules, create a variable to hold the price and
    add normal logic rules.
    """
    Form = apps.get_model("forms", "Form")
    forms_with_pricelogic = (
        Form.objects.filter(formpricelogic__isnull=False)
        .exclude(product__isnull=True)
        .distinct()
    )

    for form in forms_with_pricelogic.iterator():
        product = form.product
        rules = form.formpricelogic_set.all()

        # create a variable to hold the result.
        variable_keys = set(form.formvariable_set.values_list("key", flat=True))
        variable_key = VARIABLE_KEY
        variable_name = VARIABLE_NAME
        counter = 0
        while variable_key in variable_keys:
            counter += 1
            variable_key = f"{variable_key}{counter}"
            variable_name = f"{variable_name}{counter}"
            if counter > 100:
                raise RuntimeError(
                    "Could not generate a unique key without looping too long"
                )

        price_variable = form.formvariable_set.create(
            form_definition=None,
            name=variable_name,
            key=variable_key,
            source=FormVariableSources.user_defined,
            data_type=FormVariableDataTypes.float,
        )
        form.price_variable_key = price_variable.key
        form.save()

        max_order = (
            last_rule.order
            if (last_rule := form.formlogic_set.order_by("order").last())
            else 0
        )

        # set up regular logic rules for each price logic rule
        for rule in rules:
            max_order += 1
            form.formlogic_set.create(
                description="Converted price logic rule",
                order=max_order,
                is_advanced=True,
                json_logic_trigger=rule.json_logic_trigger,
                actions=[_assignment_action(form.price_variable_key, rule.price)],
            )

        # create one fallback rule in case none of the triggers hit
        composite_negated_trigger = {
            "!": {"or": [rule.json_logic_trigger for rule in rules]}
        }
        max_order += 1
        form.formlogic_set.create(
            description="Converted price logic rule",
            order=max_order,
            is_advanced=True,
            json_logic_trigger=composite_negated_trigger,
            actions=[_assignment_action(form.price_variable_key, product.price)],
        )

        rules.delete()


class Migration(migrations.Migration):

    replaces = [
        ("forms", "0098_form_introduction_page_content_and_more"),
        ("forms", "0099_form_show_summary_progress"),
        ("forms", "0097_extra_mimetypes_in_file_type"),
        ("forms", "0098_merge_20240920_1808"),
        ("forms", "0100_merge_20240920_1816"),
        ("forms", "0101_form_price_variable_key"),
        ("forms", "0101_fix_empty_default_value"),
        ("forms", "0102_merge_20241022_1143"),
        ("forms", "0103_remove_formvariable_prefill_config_empty_or_complete_and_more"),
        ("forms", "0104_select_datatype_string"),
        ("forms", "0105_alter_form_all_submissions_removal_limit_and_more"),
        ("forms", "0106_convert_price_logic_rules"),
        ("forms", "0107_form_submission_counter_form_submission_limit"),
    ]

    dependencies = [
        ("forms", "0097_v267_to_v270"),
    ]

    operations = [
        migrations.AddField(
            model_name="form",
            name="introduction_page_content",
            field=csp_post_processor.fields.CSPPostProcessedWYSIWYGField(
                base_field=tinymce.models.HTMLField(
                    blank=True,
                    help_text="Content for the introduction page that leads to the start page of the form. Leave blank to disable the introduction page.",
                    verbose_name="introduction page",
                ),
                blank=True,
                help_text="Content for the introduction page that leads to the start page of the form. Leave blank to disable the introduction page.",
                verbose_name="introduction page",
            ),
        ),
        migrations.AddField(
            model_name="form",
            name="introduction_page_content_en",
            field=csp_post_processor.fields.CSPPostProcessedWYSIWYGField(
                base_field=tinymce.models.HTMLField(
                    blank=True,
                    help_text="Content for the introduction page that leads to the start page of the form. Leave blank to disable the introduction page.",
                    verbose_name="introduction page",
                ),
                blank=True,
                help_text="Content for the introduction page that leads to the start page of the form. Leave blank to disable the introduction page.",
                null=True,
                verbose_name="introduction page",
            ),
        ),
        migrations.AddField(
            model_name="form",
            name="introduction_page_content_nl",
            field=csp_post_processor.fields.CSPPostProcessedWYSIWYGField(
                base_field=tinymce.models.HTMLField(
                    blank=True,
                    help_text="Content for the introduction page that leads to the start page of the form. Leave blank to disable the introduction page.",
                    verbose_name="introduction page",
                ),
                blank=True,
                help_text="Content for the introduction page that leads to the start page of the form. Leave blank to disable the introduction page.",
                null=True,
                verbose_name="introduction page",
            ),
        ),
        migrations.AddField(
            model_name="form",
            name="show_summary_progress",
            field=models.BooleanField(
                default=False,
                help_text="Whether to display the short progress summary, indicating the current step number and total amount of steps.",
                verbose_name="show summary of the progress",
            ),
        ),
        migrations.AddField(
            model_name="form",
            name="price_variable_key",
            field=models.TextField(
                blank=True,
                help_text="Key of the variable that contains the calculated submission price.",
                validators=[
                    django.core.validators.RegexValidator(
                        message="Invalid variable key. It must only contain alphanumeric characters, underscores, dots and dashes and should not be ended by dash or dot.",
                        regex=re.compile("^(\\w|\\w[\\w.\\-]*\\w)$"),
                    )
                ],
                verbose_name="price variable key",
            ),
        ),
        ConvertComponentsOperation(
            component_type="textfield",
            identifier="fix_empty_default_value",
        ),
        ConvertComponentsOperation(
            component_type="email",
            identifier="fix_empty_default_value",
        ),
        ConvertComponentsOperation(
            component_type="time",
            identifier="fix_empty_default_value",
        ),
        ConvertComponentsOperation(
            component_type="phoneNumber",
            identifier="fix_empty_default_value",
        ),
        ConvertComponentsOperation(
            component_type="textarea",
            identifier="fix_empty_default_value",
        ),
        ConvertComponentsOperation(
            component_type="iban",
            identifier="fix_empty_default_value",
        ),
        ConvertComponentsOperation(
            component_type="licenseplate",
            identifier="fix_empty_default_value",
        ),
        migrations.RemoveConstraint(
            model_name="formvariable",
            name="prefill_config_empty_or_complete",
        ),
        migrations.AddField(
            model_name="formvariable",
            name="prefill_options",
            field=models.JSONField(
                blank=True, default=dict, verbose_name="prefill options"
            ),
        ),
        migrations.AddConstraint(
            model_name="formvariable",
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(
                        models.Q(
                            ("prefill_plugin", ""),
                            ("prefill_attribute", ""),
                            ("prefill_options", {}),
                        ),
                        models.Q(
                            models.Q(("prefill_plugin", ""), _negated=True),
                            ("prefill_attribute", ""),
                            models.Q(("prefill_options", {}), _negated=True),
                            ("source", "user_defined"),
                        ),
                        models.Q(
                            models.Q(("prefill_plugin", ""), _negated=True),
                            models.Q(("prefill_attribute", ""), _negated=True),
                            ("prefill_options", {}),
                        ),
                        _connector="OR",
                    )
                ),
                name="prefill_config_component_or_user_defined",
            ),
        ),
        ConvertComponentsOperation(
            component_type="select",
            identifier="set_datatype_string",
        ),
        migrations.AlterField(
            model_name="form",
            name="all_submissions_removal_limit",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Amount of days when all submissions of this form will be permanently deleted. Leave blank to use value in General Configuration.",
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="all submissions removal limit",
            ),
        ),
        migrations.AlterField(
            model_name="form",
            name="errored_submissions_removal_limit",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Amount of days errored submissions of this form will remain before being removed. Leave blank to use value in General Configuration.",
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="errored submission removal limit",
            ),
        ),
        migrations.AlterField(
            model_name="form",
            name="incomplete_submissions_removal_limit",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Amount of days incomplete submissions of this form will remain before being removed. Leave blank to use value in General Configuration.",
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="incomplete submission removal limit",
            ),
        ),
        migrations.AlterField(
            model_name="form",
            name="successful_submissions_removal_limit",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Amount of days successful submissions of this form will remain before being removed. Leave blank to use value in General Configuration.",
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="successful submission removal limit",
            ),
        ),
        migrations.RunPython(
            code=convert_price_logic_rules_to_price_variable,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddField(
            model_name="form",
            name="submission_counter",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Counter to track how many submissions have been completed for the specific form. This works in combination with the maximum allowed submissions per form and can be reset via the frontend.",
                verbose_name="submissions counter",
            ),
        ),
        migrations.AddField(
            model_name="form",
            name="submission_limit",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Maximum number of allowed submissions per form. Leave this empty if no limit is needed.",
                null=True,
                verbose_name="maximum allowed submissions",
            ),
        ),
    ]
