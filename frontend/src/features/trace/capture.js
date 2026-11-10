export const captureLabels = {
  captured: 'Captured',
  unavailable: 'Unavailable',
  redacted: 'Redacted',
  truncated: 'Truncated',
  disabled: 'Capture disabled',
  unsupported: 'Unsupported',
  error: 'Capture error',
}

export function hasCapturedValue(value, capture) {
  return ['captured', 'truncated', 'redacted'].includes(capture?.state) && value !== undefined
}
