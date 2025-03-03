import {useField} from 'formik';
import {FormattedMessage} from 'react-intl';

import Field from 'components/admin/forms/Field';
import FormRow from 'components/admin/forms/FormRow';
import {TextInput} from 'components/admin/forms/Inputs';

const ExecutiveDepartment = () => {
  const [fieldProps] = useField('zdsUitvoerendeAfdeling');
  return (
    <FormRow>
      <Field
        name="zdsUitvoerendeAfdeling"
        label={
          <FormattedMessage
            description="StUF-ZDS registration options 'zdsUitvoerendeAfdeling' label"
            defaultMessage="Uitvoerende afdeling"
          />
        }
        helpText={
          <FormattedMessage
            description="StUF-ZDS registration options 'zdsUitvoerendeAfdeling' helpText"
            defaultMessage="Executive department for newly created Zaken in StUF-ZDS"
          />
        }
      >
        <TextInput id="id_zdsUitvoerendeAfdeling" {...fieldProps} />
      </Field>
    </FormRow>
  );
};

ExecutiveDepartment.propTypes = {};

export default ExecutiveDepartment;
