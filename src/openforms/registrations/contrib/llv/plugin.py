import json
from urllib.parse import urljoin

from django.core.exceptions import SuspiciousOperation
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.translation import gettext_lazy as _

from zgw_consumers.client import build_client

from openforms.submissions.models import Submission, SubmissionReport

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
            "soort": form_data.get("soort", "SCHOOL"),
            "vervoer": form_data.get("vervoer", "AV"),
            "eigen_vervoer": form_data.get("eigen_vervoer", None),
            "begeleiding": form_data.get("begeleiding", False),
            "onderwijs": form_data.get("onderwijs", "BO"),
            "reden": form_data.get("reden", "HANDICAP"),
            "verzamelinkomen": form_data.get("uwVerzamelinkomenIs"),
            "datum_ingang": form_data.get("startdatum"),
            "datum_einde": form_data.get("einddatum", None),
            "memo": form_data.get("memo"),
            "aanvrager": {
                "bsn": form_static_data.get("auth_bsn"),  # niet aangeleverd in bronlijst
                "voornamen": form_data.get("aanvrager_voornamen"),
                "voorvoegsel": form_data.get("aanvrager_voorvoegsels"),
                "achternaam": form_data.get("aanvrager_geslachtsnaam"),
                "geslacht": form_data.get("aanvrager_geslacht", None),
                "geboortedatum": form_data.get("aanvrager_geboortedatum", None),  # niet aangeleverd in bronlijst
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
                    "land": form_data.get("aanvrager_land", "Nederland"),
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
                    "land": form_data.get("leerlingLand", "Nederland"),
                    "coordinaten": None,
                },
            },
            "school": {
                "naam": form_data.get("schoolnaam"),
                "brin": form_data.get("schoolVestiging"),
                "vestiging": form_data.get("schoolVestiging"),
                "schoolsoort": form_data.get("schoolSoort"),
                "denominatie": form_data.get("denominatie", None),
                "adres": {
                    "straat": form_data.get("schoolStraat"),
                    "huisnummer": form_data.get("schoolHuisnummer"),
                    "huisletter": form_data.get("schoolHuisletter", None),
                    "toevoeging": form_data.get("schoolToevoeging", None),
                    "postcode": form_data.get("schoolPostcode"),
                    "plaats": form_data.get("schoolPlaats"),
                    "land": form_data.get("schoolLand", "Nederland"),
                    "coordinaten": None,
                },
            },
        }

        service = options["service"]
        with build_client(service) as client:
            if ".." in (path := options["path"]):
                raise SuspiciousOperation("Possible path traversal detected")

            # Append /nieuw to the path
            create_path = urljoin(path + "/", "nieuw")

            result = client.post(
                create_path, data=json.dumps(api_data, cls=DjangoJSONEncoder), headers={"content-type": "application/json"}
            )
            result.raise_for_status()

            result_json = result.json() if result.content else {}
            aanvraagnummer = result_json.get("nummer")

            # Upload submission report and attachments
            if aanvraagnummer:
                bijlage_path = urljoin(path + "/", "bijlage")

                # Upload submission report
                submission_report = SubmissionReport.objects.get(submission=submission)
                files = {
                    "bestand": (
                        f"{submission.public_registration_reference}.pdf",
                        submission_report.content.read(),
                        "application/pdf"
                    )
                }
                data = {
                    "aanvraagnummer": aanvraagnummer,
                    "verklaring": "AANVRAAG"
                }

                report_result = client.post(bijlage_path, data=data, files=files)
                report_result.raise_for_status()

                # Upload attachments
                for attachment in submission.attachments.order_by("pk"):
                    files = {
                        "bestand": (
                            attachment.get_display_name(),
                            attachment.content.read(),
                            attachment.content_type
                        )
                    }
                    data = {
                        "aanvraagnummer": aanvraagnummer,
                        "verklaring": "AANVRAAG"
                    }

                    attachment_result = client.post(bijlage_path, data=data, files=files)
                    attachment_result.raise_for_status()

        return {"api_response": result_json}

    def check_config(self) -> None:
        # Config checks are not really relevant for this plugin right now
        pass
