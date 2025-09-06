import base64
import json
from collections import defaultdict
from typing import cast

from django.core.exceptions import SuspiciousOperation
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import F, TextField, Value
from django.db.models.functions import Coalesce, NullIf
from django.utils.translation import gettext_lazy as _

from zgw_consumers.client import build_client

from openforms.formio.service import FormioData
from openforms.formio.typing import (
    Component,
    EditGridComponent,
    FileComponent,
)
from openforms.forms.models import FormVariable
from openforms.submissions.models import Submission, SubmissionFileAttachment
from openforms.variables.constants import FormVariableSources
from openforms.variables.service import get_static_variables

from ...base import BasePlugin  # openforms.registrations.base
from ...registry import register  # openforms.registrations.registry
from .config import LLVOptionsSerializer

PLUGIN_IDENTIFIER = 'llv'


@register(PLUGIN_IDENTIFIER)
class LLVRegistration(BasePlugin):
    verbose_name = _("LLV")
    configuration_options = LLVOptionsSerializer

    def register_submission(self, submission: Submission, options: dict) -> dict:
        state = submission.load_submission_value_variables_state()
        form_data = state.get_data()
        form_static_data = state.get_static_data()

        api_data = {
            "nummer": submission.public_registration_reference,
            "soort": "SCHOOL",
            "vervoer": "AV",
            "eigen_vervoer": None,
            "begeleiding": False,
            "onderwijs": "BO",
            "reden": "HANDICAP",
            "verzamelinkomen": form_data.get("uwVerzamelinkomenIs"),
            "datum_ingang": form_data.get("startdatum"),
            "datum_einde": None,  # niet aanwezig in bron
            "aanvrager": {
                "bsn": form_static_data.get('auth_bsn'),  # niet aangeleverd in bronlijst
                "voornamen": form_data.get("aanvrager_voornamen"),
                "voorvoegsel": form_data.get("aanvrager_voorvoegsels"),
                "achternaam": form_data.get("aanvrager_geslachtsnaam"),
                "geslacht": None,  # niet aangeleverd in bronlijst
                "geboortedatum": None,  # niet aangeleverd in bronlijst
                "telefoon": form_data.get("aanvrager_telefoonnummer"),
                "email": form_data.get("aanvrager_email"),
                "iban": form_data.get("geefUwIbanRekeningnummer"),
                "relatie": form_data.get("aanvrager_relatie"),
                "adres": {
                    "straat": form_data.get("aanvrager_straatnaam"),
                    "huisnummer": form_data.get("aanvrager_huisnummer"),
                    "huisletter": form_data.get("aanvrager_huisletter"),
                    "toevoeging": form_data.get("aanvrager_huisnrtoevoeging"),
                    "postcode": form_data.get("aanvrager_postcode"),
                    "plaats": form_data.get("woonplaats"),
                    "land": "Nederland",
                    "coordinaten": None,
                },
            },
            "leerling": {
                "bsn": form_data.get("bsn"),
                "roepnaam": form_data.get("leerlingRoepnaam"),
                "voorletters": "",
                "voornamen": form_data.get("leerlingVoornamen"),
                "voorvoegsel": form_data.get("leerlingVoorvoegsels"),
                "achternaam": form_data.get("leerlingAchternaam"),
                "geslacht": form_data.get("geslachtLeerling"),
                "geboortedatum": form_data.get("llGeboortedatum"),
                "adres": {
                    "straat": form_data.get("straatnaam"),
                    "huisnummer": form_data.get("leerlingHuisnummer"),
                    "huisletter": None,
                    "toevoeging": None,
                    "postcode": form_data.get("leerlingPostcode"),
                    "plaats": form_data.get("leerlingWoonplaats"),
                    "land": "Nederland",
                    "coordinaten": None,
                },
            },
            "school": {
                "naam": form_data.get("schoolnaam"),
                "brin": form_data.get("schoolVestiging"),
                "vestiging": form_data.get("schoolVestiging"),
                "schoolsoort": form_data.get("schoolSoort"),
                "denominatie": None,  # niet in bron
                "adres": {
                    "straat": form_data.get("schoolStraat"),
                    "huisnummer": form_data.get("schoolHuisnummer"),
                    "huisletter": None,
                    "toevoeging": None,
                    "postcode": form_data.get("schoolPostcode"),
                    "plaats": form_data.get("schoolPlaats"),
                    "land": "Nederland",
                    "coordinaten": None,
                },
            },
        }

        service = options["service"]
        with build_client(service) as client:
            if ".." in (path := options["path"]):
                raise SuspiciousOperation("Possible path traversal detected")

            result = client.post(
                path, data=json.dumps(api_data, cls=DjangoJSONEncoder), headers={"content-type": "application/json"}
            )
            result.raise_for_status()

        result_json = result.json() if result.content else ""

        return {"api_response": result_json}

    def check_config(self) -> None:
        # Config checks are not really relevant for this plugin right now
        pass
