from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from rest_framework import serializers
from zgw_consumers.constants import APITypes
from zgw_consumers.models import Service

from openforms.api.fields import PrimaryKeyRelatedAsChoicesField
from openforms.utils.mixins import JsonSchemaSerializerMixin


def validate_path(v: str) -> None:
    """Validate path by checking if it contains '..', which can lead to path traversal
    attacks.

    :param v: path to validate
    """
    if ".." in v:
        raise ValidationError(
            "Path cannot contain '..', as it can lead to path traversal attacks."
        )


class AppointmentOptionsSerializer(JsonSchemaSerializerMixin, serializers.Serializer):
    pass
