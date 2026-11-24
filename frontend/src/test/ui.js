import { screen } from '@testing-library/react'

// Radix Select: open the combobox named `name`, then pick the option by its label.
export async function chooseOption(user, name, option) {
  await user.click(screen.getByRole('combobox', { name }))
  await user.click(await screen.findByRole('option', { name: option }))
}

// The current label shown in a Radix Select trigger.
export const selectedOption = name => screen.getByRole('combobox', { name }).textContent
