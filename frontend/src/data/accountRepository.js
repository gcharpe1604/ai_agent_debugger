// Accounts on the durable backend: /api/v1/auth. The session is the backend's
// signed cookie (adbg_session), sent by the browser; nothing is stored here.
// Errors carry a kind the UI maps to its own text. Server text is never shown.
const BASE = '/api/v1/auth'

// Field messages for a 422. The backend's own messages are not displayed.
export const fieldMessages = {
  name: 'Enter a name of 80 characters or fewer.',
  email: 'Enter a valid email address.',
  password: 'Use at least 8 characters.',
}

export function accountError(kind, extra = {}) {
  return Object.assign(new Error(`Account request failed: ${kind}`), { kind, ...extra })
}

// 422 detail -> { field: our message } for the fields the form shows.
function fieldErrors(body) {
  const fields = {}
  for (const item of Array.isArray(body?.detail) ? body.detail : []) {
    const field = Array.isArray(item?.loc) ? item.loc[item.loc.length - 1] : null
    if (fieldMessages[field]) fields[field] = fieldMessages[field]
  }
  return fields
}

const isUser = value => !!value && ['id', 'name', 'email', 'key_prefix'].every(key => typeof value[key] === 'string')
const userView = value => ({ id: value.id, name: value.name, email: value.email, keyPrefix: value.key_prefix })
const isKey = value => typeof value === 'string' && value.startsWith('adbg_sk_')

export function createAccountAdapter(fetcher = fetch) {
  async function call(path, { method = 'GET', body, signal } = {}) {
    let response
    try {
      response = await fetcher(BASE + path, {
        method, signal, credentials: 'same-origin', cache: 'no-store',
        headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
        body: body ? JSON.stringify(body) : undefined,
      })
    } catch (error) {
      if (error?.name === 'AbortError') throw error
      throw accountError('unavailable')
    }
    if (response.ok) return response.status === 204 ? null : response.json()
    if (response.status === 401) throw accountError('expired', { status: 401 })
    if (response.status === 403) throw accountError('forbidden', { status: 403 })
    if (response.status === 409) throw accountError('validation', { status: 409, fields: { email: 'An account with this email already exists.' } })
    if (response.status === 422) {
      let parsed = null
      try { parsed = await response.json() } catch { /* body is not needed to report the failure */ }
      throw accountError('validation', { status: 422, fields: fieldErrors(parsed) })
    }
    // 5xx and anything unexpected: one generic kind, no server text.
    throw accountError(response.status >= 500 ? 'unavailable' : 'failure', { status: response.status })
  }
  return {
    mode: 'durable',
    async readSession({ signal } = {}) {
      try {
        const body = await call('/me', { signal })
        if (!isUser(body)) throw accountError('failure')
        return { state: 'signed-in', user: userView(body) }
      } catch (error) {
        if (error?.kind === 'expired') return { state: 'signed-out' }
        throw error
      }
    },
    async signIn({ email, password, signal }) {
      try {
        await call('/login', { method: 'POST', body: { email, password }, signal })
      } catch (error) {
        // A 401 here is a wrong email or password, not an expired session.
        if (error?.kind === 'expired') throw accountError('credentials', { status: 401 })
        throw error
      }
    },
    async register({ name, email, password, signal }) {
      const body = await call('/register', { method: 'POST', body: { name, email, password }, signal })
      if (!isUser(body?.user) || !isKey(body.api_key)) throw accountError('failure')
      return { user: userView(body.user), apiKey: body.api_key }
    },
    async signOut({ signal } = {}) {
      await call('/logout', { method: 'POST', signal })
    },
    async rotateKey({ signal } = {}) {
      const body = await call('/key/rotate', { method: 'POST', signal })
      if (!isKey(body?.api_key) || typeof body.key_prefix !== 'string') throw accountError('failure')
      return { apiKey: body.api_key, keyPrefix: body.key_prefix }
    },
  }
}
