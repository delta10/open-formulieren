import json
from datetime import date, datetime
from urllib.parse import urljoin

from django.core.exceptions import SuspiciousOperation
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.translation import gettext_lazy as _

from zgw_consumers.client import build_client

from ...exceptions import RegistrationFailed

from openforms.submissions.models import Submission, SubmissionReport

from ...base import BasePlugin  # openforms.registrations.base
from ...registry import register  # openforms.registrations.registry
from .config import LLVOptionsSerializer

PLUGIN_IDENTIFIER = 'llv'


@register(PLUGIN_IDENTIFIER)
class LLVRegistration(BasePlugin):
    verbose_name = _("LLV")
    configuration_options = LLVOptionsSerializer

    def _check_response(self, response, operation_name: str):
        """Check response and raise RegistrationFailed if not successful."""
        if not response.ok:
            error_info = f"{operation_name} failed with status {response.status_code}"
            try:
                response_data = response.json()
                error_info += f" Response: {response_data}"
            except (ValueError, json.JSONDecodeError):
                if hasattr(response, 'text'):
                    error_info += f" Response body: {response.text}"
            raise RegistrationFailed(error_info)

    def _format_datetime(self, datetime_str: str | datetime | date | None) -> str | None:
        """Convert datetime from ISO format to the format expected by LLV API."""
        if not datetime_str:
            return None
        try:
            # If already a datetime or date object, use it directly
            if isinstance(datetime_str, (datetime, date)):
                dt = datetime_str
            else:
                # Parse ISO format datetime (e.g., "2024-11-08T00:00:00-02:00")
                dt = datetime.fromisoformat(datetime_str)
            # Format to "2009-01-30T00:00:00+0100" (without colon in timezone)
            return dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            # If parsing fails, return original value
            return str(datetime_str) if datetime_str else None

    def register_submission(self, submission: Submission, options: dict) -> dict:
        state = submission.load_submission_value_variables_state()
        form_data = state.get_data()
        form_static_data = state.get_static_data()

        api_data = {
            "nummer": submission.public_registration_reference,
            "soort": form_data.get("soort", "SCHOOL"),
            "vervoer": form_data.get("vervoer", "AV"),
            "eigen_vervoer": form_data.get("eigenVervoer"),
            "begeleiding": form_data.get("begeleiding"),
            "onderwijs": form_data.get("onderwijs", "BO"),
            "reden": form_data.get("reden", "HANDICAP"),
            "verzamelinkomen": form_data.get("verzamelinkomen"),
            "datum_ingang": self._format_datetime(form_data.get("datumIngang")),
            "datum_einde": self._format_datetime(form_data.get("datumEinde")),
            "memo": form_data.get("memo"),
            "aanvrager": {
                "bsn": form_static_data.get("auth_bsn"),
                "voornamen": form_data.get("aanvragerVoornamen"),
                "voorvoegsel": form_data.get("aanvragerVoorvoegsel"),
                "achternaam": form_data.get("aanvragerAchternaam"),
                "geslacht": form_data.get("aanvragerGeslacht"),
                "geboortedatum": self._format_datetime(form_data.get("aanvragerGeboortedatum")),
                "telefoon": form_data.get("aanvragerTelefoon"),
                "email": form_data.get("aanvragerEmail"),
                "iban": form_data.get("aanvragerIban"),
                "relatie": form_data.get("aanvragerRelatie"),
                "adres": {
                    "straat": form_data.get("aanvragerStraat"),
                    "huisnummer": form_data.get("aanvragerHuisnummer"),
                    "huisletter": form_data.get("aanvragerHuisletter"),
                    "toevoeging": form_data.get("aanvragerToevoeging"),
                    "postcode": form_data.get("aanvragerPostcode"),
                    "plaats": form_data.get("aanvragerPlaats"),
                    "land": form_data.get("aanvragerLand", "Nederland")
                },
            },
            "leerling": {
                "bsn": form_data.get("leerlingBsn"),
                "roepnaam": form_data.get("leerlingRoepnaam"),
                "voorletters": form_data.get("leerlingVoorletters"),
                "voornamen": form_data.get("leerlingVoornamen"),
                "voorvoegsel": form_data.get("leerlingVoorvoegsel"),
                "achternaam": form_data.get("leerlingAchternaam"),
                "geslacht": form_data.get("leerlingGeslacht"),
                "geboortedatum": self._format_datetime(form_data.get("leerlingGeboortedatum")),
                "adres": {
                    "straat": form_data.get("leerlingStraat"),
                    "huisnummer": form_data.get("leerlingHuisnummer"),
                    "huisletter": form_data.get("leerlingHuisletter"),
                    "toevoeging": form_data.get("leerlingToevoeging"),
                    "postcode": form_data.get("leerlingPostcode"),
                    "plaats": form_data.get("leerlingPLaats"),
                    "land": form_data.get("leerlingLand", "Nederland")
                },
            },
            "school": {
                "naam": form_data.get("schoolNaam"),
                "brin": form_data.get("schoolBrin"),
                "vestiging": form_data.get("schoolVestiging"),
                "schoolsoort": form_data.get("schoolSoort")
            },
        }

        if form_data.get("dagelijks") == "nee":
            api_data["reisschema"] = {
                "weken": "ALLE",
                "toelichting": "Dit is de verduidelijking van het reisschema.",
                "maandag": {
                    "ochtend": form_data.get("maOchtend", False),
                    "middag": form_data.get("maMiddag", False),
                    "afwijkend_retour": form_data.get("maAfwijkendRetour", False),
                },
                "dinsdag": {
                    "ochtend": form_data.get("diOchtend", False),
                    "middag": form_data.get("diMiddag", False),
                    "afwijkend_retour": form_data.get("diAfwijkendRetour", False),
                },
                "woensdag": {
                    "ochtend": form_data.get("woOchtend", False),
                    "middag": form_data.get("woMiddag", False),
                    "afwijkend_retour": form_data.get("woAfwijkendRetour", False),
                },
                "donderdag": {
                    "ochtend": form_data.get("doOchtend", False),
                    "middag": form_data.get("doMiddag", False),
                    "afwijkend_retour": form_data.get("doAfwijkendRetour", False),
                },
                "vrijdag": {
                    "ochtend": form_data.get("vrOchtend", False),
                    "middag": form_data.get("vrMiddag", False),
                    "afwijkend_retour": form_data.get("vrAfwijkendRetour", False),
                },
            }

        if form_data.get("afwijkendAdresOmschrijving"):
            api_data["afwijkend_adres"] = {
                "omschrijving": form_data.get("afwijkendAdresOmschrijving"),
                "contact": form_data.get("afwijkendAdresContact"),
                "telefoon": form_data.get("afwijkendAdresTelefoon"),
                "email": form_data.get("afwijkendAdresEmail"),
                "adres": {
                    "straat": form_data.get("afwijkendAdresStraat"),
                    "huisnummer": form_data.get("afwijkendAdresHuisnummer"),
                    "huisletter": form_data.get("afwijkendAdresHuisletter"),
                    "toevoeging": form_data.get("afwijkendAdresToevoeging"),
                    "postcode": form_data.get("afwijkendAdresPostcode"),
                    "plaats": form_data.get("afwijkendAdresPlaats"),
                    "land": form_data.get("afwijkendAdresLand", "Nederland")
                }
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
            self._check_response(result, "Application creation")

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
                self._check_response(report_result, "Report upload")

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
                    self._check_response(attachment_result, "Attachment upload")

        return {"api_response": result_json}

    def check_config(self) -> None:
        # Config checks are not really relevant for this plugin right now
        pass
