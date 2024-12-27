# Generated by Django 4.2.16 on 2024-11-25 15:32

from django.db import migrations
from django.utils.module_loading import import_string

convert_price_logic_rules_to_price_variable = import_string(
    "openforms.forms.migrations"
    ".0098_v270_to_v300.convert_price_logic_rules_to_price_variable"
)


class Migration(migrations.Migration):

    dependencies = [
        ("forms", "0105_alter_form_all_submissions_removal_limit_and_more"),
    ]

    operations = [
        migrations.RunPython(
            convert_price_logic_rules_to_price_variable, migrations.RunPython.noop
        ),
    ]
