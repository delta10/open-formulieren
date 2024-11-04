import logging

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from glom import Path, PathAccessError, glom

from openforms.contrib.objects_api.checks import check_config
from openforms.contrib.objects_api.clients import get_objects_client
from openforms.contrib.objects_api.models import ObjectsAPIGroupConfig
from openforms.contrib.objects_api.ownership_validation import validate_object_ownership
from openforms.registrations.contrib.objects_api.models import ObjectsAPIConfig
from openforms.submissions.models import Submission
from openforms.typing import JSONEncodable, JSONObject

from ...base import BasePlugin
from ...registry import register
from .api.serializers import ObjectsAPIOptionsSerializer
from .typing import ObjectsAPIOptions

logger = logging.getLogger(__name__)


PLUGIN_IDENTIFIER = "objects_api"


@register(PLUGIN_IDENTIFIER)
class ObjectsAPIPrefill(BasePlugin[ObjectsAPIOptions]):
    verbose_name = _("Objects API")
    options = ObjectsAPIOptionsSerializer

    def verify_initial_data_ownership(
        self, submission: Submission, prefill_options: dict
    ) -> None:
        api_group = ObjectsAPIGroupConfig.objects.filter(
            pk=prefill_options.get("objects_api_group")
        ).first()

        if not api_group:
            logger.info(
                "No api group found to perform initial_data_reference ownership check for submission %s with options %s",
                submission,
                prefill_options,
            )
            return

        with get_objects_client(api_group) as client:
            # TODO configurable path
            validate_object_ownership(submission, client, ["bsn"])

    @classmethod
    def get_prefill_values_from_options(
        cls,
        submission: Submission,
        options: ObjectsAPIOptions,
    ) -> dict[str, JSONEncodable]:
        with get_objects_client(options["objects_api_group"]) as client:
            obj = client.get_object(submission.initial_data_reference)

        obj_record = obj.get("record", {})
        prefix = "data"

        results = {}
        for mapping in options["variables_mapping"]:
            path = Path(prefix, *mapping["target_path"])

            try:
                value = glom(obj_record, path)
            except PathAccessError:
                continue
            results[mapping["variable_key"]] = value

        return results

    def check_config(self):
        check_config()

    def get_config_actions(self):
        return [
            (
                _("Manage API groups"),
                reverse(
                    "admin:registrations_objects_api_objectsapigroupconfig_changelist"
                ),
            ),
            (
                _("Defaults configuration"),
                reverse(
                    "admin:registrations_objects_api_objectsapiconfig_change",
                    args=(ObjectsAPIConfig.singleton_instance_id,),
                ),
            ),
        ]

    @classmethod
    def configuration_context(cls) -> JSONObject | None:
        return {
            "api_groups": [
                [group.pk, group.name]
                for group in ObjectsAPIGroupConfig.objects.iterator()
            ]
        }
