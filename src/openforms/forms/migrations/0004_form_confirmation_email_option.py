# Generated by Django 2.2.24 on 2021-11-11 11:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("forms", "0003_auto_20210930_1156"),
    ]

    operations = [
        migrations.AddField(
            model_name="form",
            name="confirmation_email_option",
            field=models.CharField(
                choices=[
                    ("form_specific_email", "Form specific email"),
                    ("global_email", "Global email"),
                    ("no_email", "No email"),
                ],
                default="global_email",
                max_length=255,
                verbose_name="confirmation email option",
            ),
        ),
    ]
