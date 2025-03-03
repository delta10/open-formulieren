from typing import Literal, NotRequired, TypedDict


class MappingItem(TypedDict):
    form_variable: str
    stuf_name: str


class RegistrationOptions(TypedDict):
    zds_omschrijving: NotRequired[str]
    zds_toelichting: NotRequired[str]
    zds_zaaktype_code: str
    zds_zaaktype_omschrijving: NotRequired[str]
    zds_zaaktype_status_code: NotRequired[str]
    zds_zaaktype_status_omschrijving: NotRequired[str]
    zds_uitvoerende_afdeling: NotRequired[str]
    zds_documenttype_omschrijving_inzending: str
    zds_zaakdoc_vertrouwelijkheid: Literal[
        "ZEER GEHEIM",
        "GEHEIM",
        "CONFIDENTIEEL",
        "VERTROUWELIJK",
        "ZAAKVERTROUWELIJK",
        "INTERN",
        "BEPERKT OPENBAAR",
        "OPENBAAR",
    ]
    payment_status_update_mapping: NotRequired[list[MappingItem]]
