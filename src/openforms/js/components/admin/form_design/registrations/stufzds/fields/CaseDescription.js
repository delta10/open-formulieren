import {useField} from 'formik';
import {FormattedMessage} from 'react-intl';

import Field from 'components/admin/forms/Field';
import FormRow from 'components/admin/forms/FormRow';
import {TextInput} from 'components/admin/forms/Inputs';

const CaseDescription = () => {
  const [fieldProps] = useField('zdsOmschrijving');
  return (
    <FormRow>
      <Field
        name="zdsOmschrijving"
        label={
          <FormattedMessage
            description="StUF-ZDS registration options 'zdsOmschrijving' label"
            defaultMessage="Zaakomschrijving"
          />
        }
        helpText={
          <FormattedMessage
            description="StUF-ZDS registration options 'zdsOmschrijving' helpText"
            defaultMessage="Case description for newly created Zaken in StUF-ZDS"
          />
        }
      >
        <TextInput id="id_zdsZaakOmschrijving" {...fieldProps} />
      </Field>
    </FormRow>
  );
};

CaseDescription.propTypes = {};

export default CaseDescription;
