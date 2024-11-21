from django_setup_configuration.configuration import BaseConfigurationStep
from zgw_consumers.models import Service

from openforms.contrib.objects_api.models import ObjectsAPIGroupConfig

from .models import ObjectsAPIGroupConfigModel, SingleObjectsAPIGroupConfigModel


def get_service(slug: str) -> Service:
    """
    Try to find a Service and re-raise DoesNotExist with the identifier to make debugging
    easier
    """
    try:
        return Service.objects.get(slug=slug)
    except Service.DoesNotExist as e:
        raise Service.DoesNotExist(f"{str(e)} (identifier = {slug})")


class ObjectsAPIConfigurationStep(BaseConfigurationStep[ObjectsAPIGroupConfigModel]):
    """
    Configure configuration groups for the Objects API backend
    """

    verbose_name = "Configuration to set up Objects API registration backend services"
    config_model = ObjectsAPIGroupConfigModel
    namespace = "objects_api"
    enable_setting = "objects_api_config_enable"

    def execute(self, model: ObjectsAPIGroupConfigModel):
        config: SingleObjectsAPIGroupConfigModel
        for config in model.groups:
            defaults = {
                "name": config.name,
                "objects_service": get_service(config.objects_service_identifier),
                "objecttypes_service": get_service(
                    config.objecttypes_service_identifier
                ),
                "catalogue_domain": config.catalogue_domain,
                "catalogue_rsin": config.catalogue_rsin,
                "organisatie_rsin": config.organisatie_rsin,
                "iot_submission_report": config.iot_submission_report,
                "iot_submission_csv": config.iot_submission_csv,
                "iot_attachment": config.iot_attachment,
            }
            if config.drc_service_identifier:
                defaults["drc_service"] = get_service(config.drc_service_identifier)
            if config.catalogi_service_identifier:
                defaults["catalogi_service"] = get_service(
                    config.catalogi_service_identifier
                )

            ObjectsAPIGroupConfig.objects.update_or_create(
                identifier=config.identifier,
                defaults=defaults,
            )
