from __future__ import annotations

import datetime
import decimal
import uuid
from typing import TYPE_CHECKING, Any, NewType, Protocol, Sequence

from django.http import HttpRequest
from django.http.response import HttpResponseBase
from django.utils.functional import Promise

from rest_framework.request import Request

if TYPE_CHECKING:
    from django.utils.functional import _StrOrPromise
else:
    _StrOrPromise = str

type JSONPrimitive = str | int | float | bool | None

type JSONValue = JSONPrimitive | JSONObject | Sequence[JSONValue]

type JSONObject = dict[str, JSONValue]

type DataMapping = dict[str, Any]  # key: value pair

type AnyRequest = HttpRequest | Request

RegistrationBackendKey = NewType("RegistrationBackendKey", str)

type StrOrPromise = _StrOrPromise
"""Either ``str`` or a ``Promise`` object returned by the lazy ``gettext`` functions."""


class RequestHandler(Protocol):
    def __call__(self, request: HttpRequest) -> HttpResponseBase: ...


# Types that `django.core.serializers.json.DjangoJSONEncoder` can handle
type DjangoJSONEncodable = (
    JSONValue
    | datetime.datetime
    | datetime.date
    | datetime.time
    | datetime.timedelta
    | decimal.Decimal
    | uuid.UUID
    | Promise
)


class JSONSerializable(Protocol):
    def __json__(self) -> DjangoJSONEncodable: ...


type JSONEncodable = DjangoJSONEncodable | JSONSerializable
