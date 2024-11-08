import {expect, screen, userEvent, within} from '@storybook/test';
import {useState} from 'react';

import ActionButton from 'components/admin/forms/ActionButton';

import useConfirm from './useConfirm';

const ButtonWithUseConfirm = () => {
  const [ConfirmationModal, confirm] = useConfirm(
    'A sample confirmation message',
    'The confirmation title'
  );
  const [confirmationResult, setConfirmationResult] = useState(null);
  return (
    <div>
      <ActionButton
        text="Open confirmation modal"
        onClick={async () => {
          const result = await confirm();
          setConfirmationResult(result);
        }}
      />
      {confirmationResult !== null ? (
        <p>Confirmation result: {confirmationResult.toString()}</p>
      ) : null}
      <ConfirmationModal />
    </div>
  );
};

export default {
  title: 'Admin / Custom / UseConfirm',
  render: () => <ButtonWithUseConfirm />,
  component: useConfirm,
};

export const Default = {
  name: 'Default',

  play: async ({canvasElement, step}) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('button', {name: 'Open confirmation modal'}));

    // The confirmation modal is opened, and shows the title and message
    const confirmationModal = screen.getByRole('dialog');
    expect(confirmationModal).toBeVisible();
    expect(within(confirmationModal).getByText('The confirmation title')).toBeVisible();
    expect(within(confirmationModal).getByText('A sample confirmation message')).toBeVisible();

    await step('Closing the modal returns false', async () => {
      // Close the modal using the close button
      const closeBtn = await screen.findByRole('button', {name: 'Sluiten'});
      await userEvent.click(closeBtn);

      expect(await canvas.findByText('Confirmation result: false')).toBeVisible();
    });

    await step('Confirming the modal returns true', async () => {
      // Open the modal
      await userEvent.click(canvas.getByRole('button', {name: 'Open confirmation modal'}));

      // Close the modal using the confirm button
      const confirmBtn = await screen.findByRole('button', {name: 'Accepteren'});
      await userEvent.click(confirmBtn);

      expect(await canvas.findByText('Confirmation result: true')).toBeVisible();
    });

    await step('Cancelling the modal returns false', async () => {
      // Open the modal
      await userEvent.click(canvas.getByRole('button', {name: 'Open confirmation modal'}));

      // Close the modal using the cancel button
      const cancelBtn = await screen.findByRole('button', {name: 'Annuleren'});
      await userEvent.click(cancelBtn);

      expect(await canvas.findByText('Confirmation result: false')).toBeVisible();
    });
  },
};
