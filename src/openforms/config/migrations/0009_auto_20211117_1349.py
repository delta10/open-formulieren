# Generated by Django 2.2.24 on 2021-11-17 12:49

from django.db import migrations, models
import openforms.config.models
import tinymce.models


class Migration(migrations.Migration):

    dependencies = [
        ("config", "0008_remove_globalconfiguration_cancel_appointment_page"),
    ]

    operations = [
        migrations.AddField(
            model_name="globalconfiguration",
            name="confirmation_email_content",
            field=tinymce.models.HTMLField(
                default=openforms.config.models.get_confirmation_email_content,
                help_text="Content of the confirmation email message. Can be overridden on the form level",
                verbose_name="content",
            ),
        ),
        migrations.AddField(
            model_name="globalconfiguration",
            name="confirmation_email_subject",
            field=models.CharField(
                default=openforms.config.models.get_confirmation_email_subject,
                help_text="Subject of the confirmation email message. Can be overridden on the form level",
                max_length=1000,
                verbose_name="subject",
            ),
        ),
    ]
