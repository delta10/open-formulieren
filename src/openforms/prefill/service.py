"""
This package holds the base module structure for the pre-fill plugins used in Open Forms.

Various sources exist that can be consulted to fetch data for an active session,
where the BSN, CoC number... can be used to retrieve this data. Think of pre-filling
the address details of a person after logging in with DigiD.

The package integrates with the form builder such that it's possible to:
    a) select which pre-fill plugin to use and which value to use from the fetched
    result via the component's configuration,
    b) create a user-defined variable via the variables tab and select which pre-fill plugin
    to use and which value to use from the fetched result and
    c) define a user-defined variable via the variables tab in which the ``prefill_options``
    are configured.

Plugins can be registered using a similar approach to the registrations package. Each plugin
is responsible for exposing which attributes/data fragments are available, and for performing
the actual look-up. Plugins receive the :class:`openforms.submissions.models.Submission`
instance that represents the current form session of an end-user.

Prefill values are embedded as default values for form fields, dynamically for every
user session using the component rewrite functionality in the serializers.

So, to recap:

1. Plugins are defined and registered
2. When editing form definitions in the admin, content editors can opt-in to pre-fill
   functionality. They select the desired plugin, and then the desired attribute from
   that plugin.
3. Content editors can also define a user-defined variable and configure the plugin and
   the necessary options by selecting the desired choices for the ``prefill_options``.
4. End-user starts the form and logs in, thereby creating a session/``Submission``
5. The submission-specific form definition configuration is enhanced with the pre-filled
   form field default values.
"""

from collections import defaultdict

import elasticapm
import structlog

from openforms.formio.service import (
    FormioConfigurationWrapper,
    normalize_value_for_component,
)
from openforms.submissions.models import Submission
from openforms.submissions.models.submission_value_variable import (
    SubmissionValueVariable,
)
from openforms.typing import JSONEncodable
from openforms.variables.constants import FormVariableSources

from .registry import Registry, register as default_register
from .sources import (
    fetch_prefill_values_from_attribute,
    fetch_prefill_values_from_options,
)

logger = structlog.stdlib.get_logger(__name__)


@elasticapm.capture_span(span_type="app.prefill")
def apply_initial_data(submission: Submission, initial_data: dict[str, JSONEncodable] | None) -> None:
    """Apply initial_data passed during submission creation to the submission state.

    If initial_data is provided (a JSON object), this function will normalize
    the values according to the component types and save them as prefill data.

    This function should be called after prefill_variables to ensure initial_data
    takes precedence over plugin-based prefill.

    Components that are marked as disabled in the configuration are skipped to prevent
    security issues where users could override values that should not be modifiable.

    :param submission: The submission instance to apply initial data to.
    :param initial_data: Dictionary with component keys and their initial values.
    """
    if not initial_data:
        return

    state = submission.load_submission_value_variables_state()
    total_config_wrapper = submission.total_configuration_wrapper

    normalized_data = {}
    for key, value in initial_data.items():
        try:
            component = total_config_wrapper[key]

            # Skip disabled components to prevent security issues
            # Note: disabled is a component configuration property, not a runtime state
            if component.get("disabled"):
                logger.warning(
                    "initial_data.disabled_component_skipped",
                    submission_uuid=str(submission.uuid),
                    component_key=key,
                )
                continue

            normalized_value = normalize_value_for_component(component, value)
            normalized_data[key] = normalized_value
        except KeyError:
            # Component doesn't exist in form, skip it
            logger.warning(
                "initial_data.component_not_found",
                submission_uuid=str(submission.uuid),
                component_key=key,
            )
            continue

    if normalized_data:
        state.save_prefill_data(normalized_data)

def inject_prefill(
    configuration_wrapper: FormioConfigurationWrapper, submission: Submission
) -> None:
    """
    Mutates each component found in configuration according to the prefilled values.

    :param configuration_wrapper: The Formiojs JSON schema wrapper describing an entire
    form or an individual component within the form.
    :param submission: The :class:`openforms.submissions.models.Submission` instance
    that holds the values of the prefill data. The prefill data was fetched earlier,
    see :func:`prefill_variables`.

    The prefill values are looped over by key: value, and for each value the matching
    component is looked up to normalize it in the context of the component.
    """
    prefilled_data = submission.get_prefilled_data()
    for key, prefill_value in prefilled_data.items():
        try:
            component = configuration_wrapper[key]
        except KeyError:
            # The component to prefill is not in this step
            continue

        if not (prefill := component.get("prefill")):
            continue
        if not prefill.get("plugin"):
            continue
        if not prefill.get("attribute"):
            continue

        default_value = component.get("defaultValue")
        # 1693: we need to normalize values according to the format expected by the
        # component. For example, (some) prefill plugins return postal codes without
        # space between the digits and the letters.
        prefill_value = normalize_value_for_component(component, prefill_value)

        if prefill_value != default_value and default_value is not None:
            logger.info(
                "prefill.overwrite_non_null_default_value",
                submission_uuid=str(submission.uuid),
                component_type=component["type"],
                default_value=default_value,
                component_id=component.get("id"),
            )
        component["defaultValue"] = prefill_value


@elasticapm.capture_span(span_type="app.prefill")
def prefill_variables(submission: Submission, register: Registry | None = None) -> None:
    """Update the submission variables state with the fetched attribute values.

    For each submission value variable that need to be prefilled, the according plugin will
    be used to fetch the value. If ``register`` is not specified, the default registry instance
    will be used.
    """
    register = register or default_register

    state = submission.load_submission_value_variables_state()
    variables_to_prefill = state.get_prefill_variables()

    key_source_mappings: defaultdict[str, str] = defaultdict()
    if state.variables:
        for variable_key, variable in state.variables.items():
            assert variable.form_variable is not None
            key_source_mappings[variable_key] = variable.form_variable.source

    variables_with_attribute: list[SubmissionValueVariable] = []
    variables_with_options: list[SubmissionValueVariable] = []
    prefill_data: defaultdict[str, JSONEncodable] = defaultdict(dict)

    for variable in variables_to_prefill:
        assert variable.form_variable is not None
        key_source_mappings[variable.form_variable.key] = variable.form_variable.source
        # variables which have prefill enabled via the component's configuration
        if (
            variable.form_variable.source == FormVariableSources.component
            and variable.form_variable.prefill_plugin
            and variable.form_variable.prefill_attribute
        ):
            variables_with_attribute.append(variable)

        if variable.form_variable.source == FormVariableSources.user_defined:
            # variables which have prefill enabled via the variables tab and define prefill options
            if (
                variable.form_variable.prefill_plugin
                and variable.form_variable.prefill_options
            ):
                variables_with_options.append(variable)

            # variables which have prefill enabled via the variables tab and define prefill attribute
            if (
                variable.form_variable.prefill_plugin
                and variable.form_variable.prefill_attribute
            ):
                variables_with_attribute.append(variable)

    if variables_with_attribute and (
        results_from_attribute := fetch_prefill_values_from_attribute(
            submission, register, variables_with_attribute
        )
    ):
        prefill_data.update(**results_from_attribute)
    if variables_with_options and (
        results_from_options := fetch_prefill_values_from_options(
            submission, register, variables_with_options
        )
    ):
        prefill_data.update(**results_from_options)

    total_config_wrapper = submission.total_configuration_wrapper
    for variable_key, prefill_value in prefill_data.items():
        if key_source_mappings[variable_key] == FormVariableSources.component:
            component = total_config_wrapper[variable_key]
            normalized_prefill_value = normalize_value_for_component(
                component, prefill_value
            )
            prefill_value = normalized_prefill_value

        prefill_data[variable_key] = prefill_value

    state.save_prefill_data(prefill_data)
