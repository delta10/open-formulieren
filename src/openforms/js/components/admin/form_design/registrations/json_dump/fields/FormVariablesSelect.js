import {useField} from 'formik';
import PropTypes from 'prop-types';
import React from 'react';
import {FormattedMessage} from 'react-intl';

import Field from 'components/admin/forms/Field';
import FormRow from 'components/admin/forms/FormRow';
import ReactSelect from 'components/admin/forms/ReactSelect';

const FormVariablesSelect = ({options}) => {
  const [fieldProps, , {setValue}] = useField('variables');

  const values = [];
  if (fieldProps.value && fieldProps.value.length) {
    fieldProps.value.forEach(item => {
      const selectedOption = options.find(option => option.value === item);
      if (selectedOption) {
        values.push(selectedOption);
      }
    });
  }

  return (
    <FormRow>
      <Field
        name="variables"
        label={
          <FormattedMessage
            description="JSON registration options 'variables' label"
            defaultMessage="Variables"
          />
        }
        helpText={
          <FormattedMessage
            description="JSON registration options 'variables' helpText"
            defaultMessage="Which variables to include in the data to be sent"
          />
        }
        required
        noManageChildProps
      >
        <ReactSelect
          name="variables"
          options={options}
          isMulti
          required
          value={values}
          onChange={newValue => {
            setValue(newValue.map(item => item.value));
          }}
        />
      </Field>
    </FormRow>
  );
};

FormVariablesSelect.propTypes = {
  options: PropTypes.arrayOf(
    PropTypes.shape({
      value: PropTypes.string.isRequired,
      label: PropTypes.node.isRequired,
    })
  ).isRequired,
};

export default FormVariablesSelect;
