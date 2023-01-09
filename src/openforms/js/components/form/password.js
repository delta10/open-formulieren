import {Formio} from 'react-formio';

import {AUTOCOMPLETE, DEFAULT_VALUE} from './edit/options';
import {
  ADVANCED,
  DEFAULT_SENSITIVE_TABS,
  REGISTRATION,
  SENSITIVE_BASIC,
  TRANSLATIONS,
  VALIDATION,
} from './edit/tabs';

class PasswordField extends Formio.Components.components.password {
  static editForm() {
    return {
      components: [
        {
          ...DEFAULT_SENSITIVE_TABS,
          components: [
            {
              ...SENSITIVE_BASIC,
              components: SENSITIVE_BASIC.components.filter(
                option => option.key !== DEFAULT_VALUE.key
              ),
            },
            ADVANCED,
            VALIDATION,
            REGISTRATION,
            TRANSLATIONS,
          ],
        },
      ],
    };
  }
}

export default PasswordField;
