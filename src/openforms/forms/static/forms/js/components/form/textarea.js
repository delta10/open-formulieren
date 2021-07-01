import {Formio} from 'react-formio';

import {ADVANCED, BASIC, VALIDATION} from './edit/tabs';


const TextAreaBasicTab = {
    key: 'basic',
    label: 'Basic',
    components: [
        ...BASIC.components,
        {
            type: 'number',
            input: true,
            weight: 80,
            key: 'rows',
            label: 'Number of rows',
            tooltip: 'The number of rows for this text area.'
        }
    ]
};


const TextAreaTabs = {
    type: 'tabs',
    key: 'tabs',
    components: [
        TextAreaBasicTab,
        ADVANCED,
        VALIDATION,
    ]
};


class TextArea extends Formio.Components.components.textarea {

    static editForm() {
        return {components: [TextAreaTabs]};
    }

}

export default TextArea;
