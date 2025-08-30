import PropTypes from 'prop-types';
import {useContext} from 'react';
import {FormattedMessage} from 'react-intl';
import {TabList, TabPanel, Tabs} from 'react-tabs';

import Tab from 'components/admin/form_design/Tab';
import Fieldset from 'components/admin/forms/Fieldset';
import {
  ValidationErrorContext,
  ValidationErrorsProvider,
  filterErrors,
} from 'components/admin/forms/ValidationErrors';
import {getChoicesFromSchema} from 'utils/json-schema';

import CaseDescription from './fields/CaseDescription';
import CaseExplanation from './fields/CaseExplanation';
import CaseTypeCode from './fields/CaseTypeCode';
import CaseTypeDescription from './fields/CaseTypeDescription';
import DocumentConfidentialityLevel from './fields/DocumentConfidentialityLevel';
import DocumentTypeDescription from './fields/DocumentTypeDescription';
import PaymentStatusUpdateMapping from './fields/PaymentStatusUpdateMapping';
import StatusTypeCode from './fields/StatusTypeCode';
import StatusTypeDescription from './fields/StatusTypeDescription';
import ExecutiveDepartment from './fields/ExecutiveDepartment';

const StufZDSOptionsFormFields = ({name, schema}) => {
  const validationErrors = useContext(ValidationErrorContext);

  const {zdsZaakdocVertrouwelijkheid} = schema.properties;
  const zdsZaakdocVertrouwelijkheidChoices = getChoicesFromSchema(
    zdsZaakdocVertrouwelijkheid.enum,
    zdsZaakdocVertrouwelijkheid.enumNames
  ).map(([value, label]) => ({value, label}));

  const relevantErrors = filterErrors(name, validationErrors);
  const numPaymentStatusMappingErrors = filterErrors(
    `${name}.paymentStatusUpdateMapping`,
    validationErrors
  ).length;
  const numBaseErrors = relevantErrors.length - numPaymentStatusMappingErrors;
  return (
    <ValidationErrorsProvider errors={relevantErrors}>
      <Tabs>
        <TabList>
          <Tab hasErrors={numBaseErrors > 0}>
            <FormattedMessage
              description="StUF-ZDS registration backend options, 'base' tab label"
              defaultMessage="Base"
            />
          </Tab>
          <Tab hasErrors={numPaymentStatusMappingErrors > 0}>
            <FormattedMessage
              description="StUF-ZDS registration backend options, 'extra elements' tab label"
              defaultMessage="Extra elements"
            />
          </Tab>
        </TabList>

        <TabPanel>
          <Fieldset>
            <CaseDescription />
            <CaseExplanation />
            <CaseTypeCode />
            <CaseTypeDescription />
            <StatusTypeCode />
            <StatusTypeDescription />
            <DocumentTypeDescription />
            <DocumentConfidentialityLevel options={zdsZaakdocVertrouwelijkheidChoices} />
            <ExecutiveDepartment />
          </Fieldset>
        </TabPanel>

        <TabPanel>
          <Fieldset
            title={
              <FormattedMessage
                description="StUF-ZDS registration paymentStatusUpdateMapping label"
                defaultMessage="Payment status update variable mapping"
              />
            }
            fieldNames={['paymentStatusUpdateMapping']}
          >
            <div className="description">
              <FormattedMessage
                description="StUF-ZDS registration paymentStatusUpdateMapping message"
                defaultMessage={`This mapping is used to map the variable keys to keys
                used in the XML that is sent to StUF-ZDS. Those keys and the values
                belonging to them in the submission data are included in <code>extraElementen</code>.
              `}
                values={{
                  code: chunks => <code>{chunks}</code>,
                }}
              />
            </div>
            <PaymentStatusUpdateMapping />
          </Fieldset>
        </TabPanel>
      </Tabs>
    </ValidationErrorsProvider>
  );
};

StufZDSOptionsFormFields.propTypes = {
  name: PropTypes.string.isRequired,
  schema: PropTypes.shape({
    type: PropTypes.oneOf(['object']), // it's the JSON schema root, it has to be
    properties: PropTypes.object,
    required: PropTypes.arrayOf(PropTypes.string),
  }).isRequired,
};

export default StufZDSOptionsFormFields;
