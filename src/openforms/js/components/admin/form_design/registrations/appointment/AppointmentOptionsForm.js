import {useField} from 'formik';
import PropTypes from 'prop-types';
import React, {useContext} from 'react';
import {FormattedMessage} from 'react-intl';

import Field from 'components/admin/forms/Field';
import Fieldset from 'components/admin/forms/Fieldset';
import FormRow from 'components/admin/forms/FormRow';
import {TextInput} from 'components/admin/forms/Inputs';
import {getChoicesFromSchema} from 'utils/json-schema';
import ModalOptionsConfiguration from 'components/admin/forms/ModalOptionsConfiguration';
import {
  ValidationErrorContext,
  ValidationErrorsProvider,
  filterErrors,
} from 'components/admin/forms/ValidationErrors';

import {
  Path,
  ServiceSelect,
} from './fields';

const LLVOptionsForm = ({name, label, schema, formData, onChange}) => {
  const validationErrors = useContext(ValidationErrorContext);
  const relevantErrors = filterErrors(name, validationErrors);

  // Create service options
  const {service} = schema.properties;
  const serviceOptions = getChoicesFromSchema(service.enum, service.enumNames).map(
    ([value, label]) => ({value, label})
  );

  return (
    <ModalOptionsConfiguration
      name={name}
      label={label}
      numErrors={relevantErrors.length}
      modalTitle={
        <FormattedMessage
          description="LLV registration options modal title"
          defaultMessage="Plugin configuration: llv"
        />
      }
      initialFormData={{extraLine: '', ...formData}}
      onSubmit={values => onChange({formData: values})}
      modalSize="small"
    >
      <ValidationErrorsProvider errors={relevantErrors}>
        <Fieldset>
          <ServiceSelect options={serviceOptions} />
          <Path />
        </Fieldset>
      </ValidationErrorsProvider>
    </ModalOptionsConfiguration>
  );
};

AppointmentOptionsForm.propTypes = {
  name: PropTypes.string.isRequired,
  label: PropTypes.node.isRequired,
  formData: PropTypes.shape({
    service: PropTypes.number,
    path: PropTypes.string,
  }),
  onChange: PropTypes.func.isRequired,
};

export default AppointmentOptionsForm;
