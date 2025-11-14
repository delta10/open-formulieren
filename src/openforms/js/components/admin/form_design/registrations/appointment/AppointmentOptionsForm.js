import PropTypes from 'prop-types';
import {useContext} from 'react';
import {FormattedMessage} from 'react-intl';

import {getChoicesFromSchema} from 'utils/json-schema';
import ModalOptionsConfiguration from 'components/admin/forms/ModalOptionsConfiguration';
import {
  ValidationErrorContext,
  ValidationErrorsProvider,
  filterErrors,
} from 'components/admin/forms/ValidationErrors';

const AppointmentOptionsForm = ({name, label, schema, formData, onChange}) => {
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
          description="Appointment registration options modal title"
          defaultMessage="Plugin configuration: appointment"
        />
      }
      initialFormData={{extraLine: '', ...formData}}
      onSubmit={values => onChange({formData: values})}
      modalSize="small"
    >
      <ValidationErrorsProvider errors={relevantErrors}>
      </ValidationErrorsProvider>
    </ModalOptionsConfiguration>
  );
};

AppointmentOptionsForm.propTypes = {
  name: PropTypes.string.isRequired,
  label: PropTypes.node.isRequired,
  formData: PropTypes.shape({}),
  onChange: PropTypes.func.isRequired,
};

export default AppointmentOptionsForm;
