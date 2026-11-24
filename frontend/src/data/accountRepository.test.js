import { describe, it, expect, vi } from 'vitest'
import { createAccountAdapter, fieldMessages } from './accountRepository.js'
import { createDurableAdapters } from './durableRepository.js'

const me = { id: '6f1c0d52-0000-4000-8000-000000000001', name: 'Ada Lovelace', email: 'ada@example.com', key_prefix: 'adbg_sk_AbCd' }
const KEY = 'adbg_sk_' + 'k'.repeat(43)
const answer = (status, body) => ({ ok: status >= 200 && status < 300, status, json: async () => body })
// A server error body the UI must never show.
const leaky = { detail: 'Traceback: psycopg.OperationalError at 10.0.0.5 password=hunter2' }

function adapterFor(...responses) {
  const fetcher = vi.fn(async () => { const next = responses.shift(); if (next instanceof Error || next instanceof DOMException) throw next; return next })
  return { fetcher, adapter: createAccountAdapter(fetcher) }
}
const kindOf = promise => promise.then(() => 'resolved', error => error.kind)

describe('account adapter requests', () => {
  it('reads the session with the cookie and maps the user', async () => {
    const { fetcher, adapter } = adapterFor(answer(200, me))
    expect(adapter.mode).toBe('durable')
    expect(await adapter.readSession()).toEqual({ state: 'signed-in', user: { id: me.id, name: 'Ada Lovelace', email: 'ada@example.com', keyPrefix: 'adbg_sk_AbCd' } })
    const [url, init] = fetcher.mock.calls[0]
    expect(url).toBe('/api/v1/auth/me')
    expect(init).toMatchObject({ method: 'GET', credentials: 'same-origin', cache: 'no-store' })
    expect(init.body).toBeUndefined()
  })

  it('posts login, register, logout and rotate with JSON bodies only where needed', async () => {
    const { fetcher, adapter } = adapterFor(answer(204), answer(201, { user: me, api_key: KEY }), answer(204), answer(200, { api_key: KEY, key_prefix: KEY.slice(0, 12) }))
    await adapter.signIn({ email: 'ada@example.com', password: 'correct horse' })
    expect(await adapter.register({ name: 'Ada Lovelace', email: 'ada@example.com', password: 'correct horse' })).toEqual({ user: expect.objectContaining({ keyPrefix: 'adbg_sk_AbCd' }), apiKey: KEY })
    await adapter.signOut()
    expect(await adapter.rotateKey()).toEqual({ apiKey: KEY, keyPrefix: KEY.slice(0, 12) })
    const calls = fetcher.mock.calls.map(([url, init]) => [init.method, url, init.body && JSON.parse(init.body), init.credentials, init.headers['Content-Type']])
    expect(calls).toEqual([
      ['POST', '/api/v1/auth/login', { email: 'ada@example.com', password: 'correct horse' }, 'same-origin', 'application/json'],
      ['POST', '/api/v1/auth/register', { name: 'Ada Lovelace', email: 'ada@example.com', password: 'correct horse' }, 'same-origin', 'application/json'],
      ['POST', '/api/v1/auth/logout', undefined, 'same-origin', undefined],
      ['POST', '/api/v1/auth/key/rotate', undefined, 'same-origin', undefined],
    ])
  })
})

describe('account adapter error mapping', () => {
  it('401: signed out on a session read, wrong credentials on login, expired on rotate', async () => {
    expect(await adapterFor(answer(401, { detail: 'Not authenticated' })).adapter.readSession()).toEqual({ state: 'signed-out' })
    expect(await kindOf(adapterFor(answer(401, { detail: 'Invalid email or password' })).adapter.signIn({ email: 'a@b.co', password: 'x' }))).toBe('credentials')
    expect(await kindOf(adapterFor(answer(401, {})).adapter.rotateKey())).toBe('expired')
  })

  it('403 is forbidden, 409 an email field error, 422 our own field messages', async () => {
    expect(await kindOf(adapterFor(answer(403, { detail: 'Sign-up is disabled' })).adapter.register({}))).toBe('forbidden')
    const taken = await adapterFor(answer(409, { detail: 'Email already registered' })).adapter.register({}).catch(error => error)
    expect(taken).toMatchObject({ kind: 'validation', status: 409, fields: { email: 'An account with this email already exists.' } })
    const invalid = await adapterFor(answer(422, { detail: [
      { loc: ['body', 'password'], msg: 'String should have at least 8 characters', type: 'string_too_short' },
      { loc: ['body', 'name'], msg: 'server wording', type: 'value_error' },
      { loc: ['body', 'unknown_field'], msg: 'ignored', type: 'extra_forbidden' },
    ] })).adapter.register({}).catch(error => error)
    expect(invalid).toMatchObject({ kind: 'validation', status: 422, fields: { password: fieldMessages.password, name: fieldMessages.name } })
    expect(JSON.stringify(invalid.fields)).not.toContain('server wording')
    // A 422 without a usable body is still a validation failure, just without fields.
    const bare = await adapterFor({ ok: false, status: 422, json: async () => { throw new SyntaxError('not json') } }).adapter.signIn({}).catch(error => error)
    expect(bare).toMatchObject({ kind: 'validation', fields: {} })
  })

  it('5xx and network failures are unavailable and carry no server text', async () => {
    for (const response of [answer(500, leaky), answer(503, leaky), new TypeError('Failed to fetch')]) {
      const error = await adapterFor(response).adapter.readSession().catch(caught => caught)
      expect(error.kind).toBe('unavailable')
      expect(JSON.stringify({ message: error.message, ...error })).not.toMatch(/Traceback|hunter2|10\.0\.0\.5|Failed to fetch/)
    }
    expect(await kindOf(adapterFor(answer(418, leaky)).adapter.signOut())).toBe('failure')
  })

  it('rejects a response that does not look like a user or key', async () => {
    expect(await kindOf(adapterFor(answer(200, { name: 'no id' })).adapter.readSession())).toBe('failure')
    expect(await kindOf(adapterFor(answer(201, { user: me, api_key: 'sk-other' })).adapter.register({}))).toBe('failure')
    expect(await kindOf(adapterFor(answer(200, { api_key: KEY })).adapter.rotateKey())).toBe('failure')
  })

  it('lets an abort through unchanged', async () => {
    const abort = new DOMException('Aborted', 'AbortError')
    await expect(adapterFor(abort).adapter.readSession()).rejects.toBe(abort)
  })
})

describe('durable data reads', () => {
  it('a 401 calls onUnauthorized and throws kind expired', async () => {
    const onUnauthorized = vi.fn()
    const fetcher = vi.fn(async () => answer(401, { detail: 'Not authenticated' }))
    const { projectAdapter } = createDurableAdapters(fetcher, { onUnauthorized })
    await expect(projectAdapter.listProjects()).rejects.toMatchObject({ kind: 'expired' })
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
    expect(fetcher.mock.calls[0][1]).toMatchObject({ credentials: 'same-origin' })
  })
})
