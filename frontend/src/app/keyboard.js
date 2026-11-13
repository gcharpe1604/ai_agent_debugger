// Single-key shortcuts (/, J, K, Esc) must not fire while the user types.
export const isTyping = target => !!target?.closest?.('input, textarea, select, [contenteditable="true"]')
export const hasModifier = event => event.ctrlKey || event.metaKey || event.altKey
