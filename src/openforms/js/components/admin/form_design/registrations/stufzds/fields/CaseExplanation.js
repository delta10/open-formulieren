import {useField} from 'formik';
import {FormattedMessage} from 'react-intl';

import Field from 'components/admin/forms/Field';
import FormRow from 'components/admin/forms/FormRow';
import {TextInput} from 'components/admin/forms/Inputs';

const CaseExplanation = () => {
  const [fieldProps] = useField('zdsToelichting');
  return (
    <FormRow>
      <Field
        name="zdsToelichting"
        label={
          <FormattedMessage
            description="StUF-ZDS registration options 'zdsToelichting' label"
            defaultMessage="Zaaktoelichting"
          />
        }
        helpText={
          <FormattedMessage
            description="StUF-ZDS registration options 'zdsToelichting' helpText"
            defaultMessage="Case expanation for newly created Zaken in StUF-ZDS"
          />
        }
      >
        <TextInput id="id_zdsZaakToelichting" {...fieldProps} />
      </Field>
    </FormRow>
  );
};

CaseExplanation.propTypes = {};

export default CaseExplanation;
