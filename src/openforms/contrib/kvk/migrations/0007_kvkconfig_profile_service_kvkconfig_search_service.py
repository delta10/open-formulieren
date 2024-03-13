# Generated by Django 4.2.10 on 2024-03-12 10:10

from django.conf import settings
from django.core.cache import caches
import django.db.models.deletion
from django.db import migrations, models


def set_kvk_service(apps, _):
    """
    Derive the API root for KVK interaction.

    This used to be configured in one Service. Due to possible gateways we have to go for
    two separate Services since we need to provide different urls. The API root url can
    be the same for both operations so in this case we use one Service configuration.
    """
    KVKConfig = apps.get_model("kvk", "KVKConfig")
    config = KVKConfig.objects.first()
    if config is None:
        return

    if not (service := config.service) or not (root := service.api_root):
        return

    if "zoeken" in root:
        config.search_service = service
    elif "basisprofielen" in root:
        config.profile_service = service
    else:
        # case where we have defined generic API root url (e.g. https://kvk.nl/test/api/)
        config.search_service = service
        config.profile_service = service

    config.save()
    caches[settings.SOLO_CACHE].clear()


class Migration(migrations.Migration):

    dependencies = [
        ("zgw_consumers", "0020_service_timeout"),
        ("kvk", "0006_remove_refactored_service_config_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="kvkconfig",
            name="profile_service",
            field=models.OneToOneField(
                blank=True,
                help_text="Service for API used to retrieve basis profielen.",
                limit_choices_to={"api_type": "orc"},
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="zgw_consumers.service",
                verbose_name="KvK API Basisprofiel",
            ),
        ),
        migrations.AddField(
            model_name="kvkconfig",
            name="search_service",
            field=models.OneToOneField(
                blank=True,
                help_text="Service for API used for validation of KvK, RSIN and vestigingsnummer's.",
                limit_choices_to={"api_type": "orc"},
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="zgw_consumers.service",
                verbose_name="KvK API Zoeken",
            ),
        ),
        migrations.RunPython(set_kvk_service, migrations.RunPython.noop),
    ]
