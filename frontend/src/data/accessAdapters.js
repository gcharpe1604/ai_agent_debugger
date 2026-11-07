// Frontend view adapters, NOT HTTP endpoints, wire schemas or authorization rules.
// The disconnected adapter neither verifies credentials nor fabricates a session.
export const disconnectedAccount = Object.freeze({
  async readSession() { return { state: 'unavailable' } },
  async signIn() { throw Object.assign(new Error('Authentication is not connected.'), { kind: 'disconnected' }) },
  async register() { throw Object.assign(new Error('Registration is not connected.'), { kind: 'disconnected' }) },
  async signOut() { throw Object.assign(new Error('Session revocation is not connected.'), { kind: 'disconnected' }) },
})

export function projectNameError(value) {
  if (!value.trim()) return 'Enter a project name.'
  if (value.trim().length > 100) return 'Use 100 characters or fewer for this project.'
  return ''
}

export function failureKind(error) {
  return ['forbidden', 'expired', 'unavailable', 'disconnected'].includes(error?.kind) ? error.kind : 'failure'
}
