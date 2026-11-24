import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App.jsx'
import { createApiAdapters } from '../data/apiRepository.js'
import { expireSession } from './routes.jsx'

const ADA = { id: '6f1c0d52-0000-4000-8000-000000000001', name: 'Ada Lovelace', email: 'ada@example.com' }
const KEY_1 = 'adbg_sk_' + 'A'.repeat(43), KEY_2 = 'adbg_sk_' + 'B'.repeat(43)
const json = (status, body) => ({ ok: status >= 200 && status < 300, status, json: async () => body })
const leaky = { detail: 'Traceback: psycopg.OperationalError password=hunter2' }

// The durable backend as the UI sees it: a session cookie (here, `signedIn`),
// /auth routes and the read API. `readStatus` forces a status on data reads.
function backend({ signedIn = false, readStatus = null, register = null, me = null } = {}) {
  const state = { user: signedIn ? { ...ADA, key_prefix: KEY_1.slice(0, 12) } : null, key: KEY_1 }
  const fetcher = vi.fn(async (url, init = {}) => {
    const method = init.method || 'GET', path = url.split('?')[0]
    const body = init.body ? JSON.parse(init.body) : null
    if (method === 'GET' && path === '/api/v1/auth/me') return me || (state.user ? json(200, state.user) : json(401, { detail: 'Not authenticated' }))
    if (method === 'POST' && path === '/api/v1/auth/login') {
      if (body.email !== ADA.email || body.password !== 'correct horse battery') return json(401, { detail: 'Invalid email or password' })
      state.user = { ...ADA, key_prefix: state.key.slice(0, 12) }; return json(204)
    }
    if (method === 'POST' && path === '/api/v1/auth/register') {
      if (register) return register
      state.user = { ...ADA, name: body.name, email: body.email, key_prefix: KEY_1.slice(0, 12) }
      return json(201, { user: state.user, api_key: KEY_1 })
    }
    if (method === 'POST' && path === '/api/v1/auth/logout') { state.user = null; return json(204) }
    if (method === 'POST' && path === '/api/v1/auth/key/rotate') {
      if (!state.user) return json(401, {})
      state.key = KEY_2; state.user = { ...state.user, key_prefix: KEY_2.slice(0, 12) }
      return json(200, { api_key: KEY_2, key_prefix: KEY_2.slice(0, 12) })
    }
    if (path.startsWith('/api/v1/projects')) {
      if (!state.user) return json(401, { detail: 'Not authenticated' })
      if (readStatus && path !== '/api/v1/projects') return json(readStatus, leaky)
      if (path === '/api/v1/projects') return json(200, [{ id: 'default', name: state.user.name }])
      if (path === '/api/v1/projects/default/runs') return json(200, { project: 'default', runs: [], next_cursor: null })
    }
    throw new Error(`unexpected ${method} ${url}`)
  })
  return { fetcher, state }
}

function start(path, options) {
  window.history.replaceState(null, '', '/#' + path)
  const server = backend(options)
  render(<App {...createApiAdapters(server.fetcher, { source: 'durable', onUnauthorized: () => expireSession() })}/>)
  return { ...server, user: userEvent.setup() }
}
const calls = fetcher => fetcher.mock.calls.map(([url, init]) => `${init?.method || 'GET'} ${url}`)

describe('durable session gate', () => {
  it('sends a logged-out start to sign in and reads no project data', async () => {
    const { fetcher } = start('/projects/default/runs')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeTruthy()
    expect(window.location.hash).toBe('#/account/login?returnTo=%2Fprojects%2Fdefault%2Fruns')
    expect(calls(fetcher)).toEqual(['GET /api/v1/auth/me'])
  })

  it('signs in, returns to the requested page, shows the user and signs out', async () => {
    const { fetcher, user } = start('/projects/default/runs')
    await screen.findByRole('heading', { name: 'Sign in' })
    await user.type(screen.getByLabelText('Email'), ADA.email)
    await user.type(screen.getByLabelText('Password', { exact: true }), 'wrong password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect((await screen.findByRole('alert')).textContent).toBe('Incorrect email or password. Your password has been cleared.')
    await user.type(screen.getByLabelText('Password', { exact: true }), 'correct horse battery')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { name: 'No traces yet' })).toBeTruthy()
    expect(window.location.hash).toBe('#/projects/default/runs')
    // The user, appearance and Sign out live in the sidebar footer menu, not the top bar.
    const topbar = within(document.querySelector('.topbar'))
    expect(topbar.queryByText('Ada Lovelace')).toBeNull()
    expect(topbar.queryByRole('button', { name: 'Sign out' })).toBeNull()
    await user.click(screen.getByLabelText('Account menu: Ada Lovelace'))
    const menu = within(await screen.findByRole('menu'))
    expect(menu.getByText(ADA.email)).toBeTruthy()
    expect(menu.getByRole('group', { name: 'Theme' })).toBeTruthy()
    await user.click(menu.getByRole('menuitem', { name: 'Sign out' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeTruthy()
    expect(window.location.hash).toBe('#/account/login?returnTo=%2Fprojects%2Fdefault')
    expect(calls(fetcher)).toContain('POST /api/v1/auth/logout')
    expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0)
  })

  it('sends a 401 on a data read to session-expired with a way back', async () => {
    const { user, state } = start('/projects/default/runs', { signedIn: true })
    expect(await screen.findByRole('heading', { name: 'No traces yet' })).toBeTruthy()
    state.user = null // the session ends on the server
    await user.click(screen.getByRole('button', { name: /Refresh/ }))
    expect(await screen.findByRole('heading', { name: 'Session expired' })).toBeTruthy()
    expect(window.location.hash).toBe('#/account/session-expired?returnTo=%2Fprojects%2Fdefault%2Fruns')
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('#/account/login?returnTo=%2Fprojects%2Fdefault%2Fruns')
  })

  it('reports an unreachable backend without server text and retries', async () => {
    const { fetcher, user } = start('/projects/default/runs', { me: json(503, leaky) })
    expect(await screen.findByRole('heading', { name: 'Could not check your session' })).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/Traceback|hunter2/)
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(calls(fetcher).filter(call => call === 'GET /api/v1/auth/me')).toHaveLength(2))
  })
})

describe('registration', () => {
  async function fillRegistration(user) {
    await user.type(await screen.findByLabelText('Name', { exact: true }), 'Ada Lovelace')
    await user.type(screen.getByLabelText('Email'), ADA.email)
    await user.click(screen.getByRole('button', { name: 'Continue', exact: true }))
    await user.type(screen.getByLabelText('Password', { exact: true }), 'correct horse battery')
    await user.type(screen.getByLabelText('Confirm password', { exact: true }), 'correct horse battery')
    await user.click(screen.getByRole('checkbox', { name: 'I agree to the Terms and Conditions' }))
    await user.click(screen.getByRole('button', { name: 'Create account' }))
  }

  it('shows the API key once with the SDK setup, then continues to the runs page', async () => {
    const { fetcher, user } = start('/account/register')
    await fillRegistration(user)
    expect(await screen.findByRole('heading', { name: 'Your API key' })).toBeTruthy()
    expect(screen.getByRole('note').textContent).toContain('You won’t see this again')
    expect(screen.getByText(KEY_1)).toBeTruthy()
    expect(screen.getByText(`AGENT_DEBUGGER_ENDPOINT=http://127.0.0.1:8008/api/v1/traces AGENT_DEBUGGER_API_KEY=${KEY_1}`, { normalizer: text => text.replace(/\s+/g, ' ') })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Copy API key' })).toBeTruthy()
    const register = fetcher.mock.calls.find(([url]) => url === '/api/v1/auth/register')
    expect(JSON.parse(register[1].body)).toEqual({ name: 'Ada Lovelace', email: ADA.email, password: 'correct horse battery' })
    // Shown from component state only: never in the URL or browser storage.
    expect(window.location.href).not.toContain(KEY_1)
    expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0)
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    expect(await screen.findByRole('heading', { name: 'No traces yet' })).toBeTruthy()
    expect(window.location.hash).toBe('#/projects/default/runs')
    expect(screen.queryByText(KEY_1)).toBeNull()
    expect(screen.getByLabelText('Account menu: Ada Lovelace')).toBeTruthy()
  })

  it.each([
      ['409', json(409, { detail: 'Email already registered' }), async () => {
        expect(await screen.findByText('An account with this email already exists.')).toBeTruthy()
        expect(screen.getByLabelText('Email').getAttribute('aria-invalid')).toBe('true') // back on step 1
      }],
      ['422', json(422, { detail: [{ loc: ['body', 'password'], msg: 'server wording', type: 'string_too_short' }] }), async () => {
        expect(await screen.findByText('Use at least 8 characters.')).toBeTruthy()
        expect(screen.queryByText('server wording')).toBeNull()
      }],
      ['403', json(403, { detail: 'Sign-up is disabled' }), async () => {
        expect((await screen.findByRole('alert')).textContent).toContain('Sign-up is turned off on this server')
      }],
      ['500', json(500, leaky), async () => {
        expect((await screen.findByRole('alert')).textContent).toContain('The backend did not answer')
        expect(document.body.textContent).not.toMatch(/Traceback|hunter2/)
      }],
  ])('maps a %s to a field error or a fixed message and creates no session', async (_, answer, check) => {
    const { user, state } = start('/account/register', { register: answer })
    await fillRegistration(user)
    await check()
    expect(state.user).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Your API key' })).toBeNull()
  })
})

describe('settings', () => {
  it('shows General and API key tabs, a placeholder snippet, and rotates the key only after confirmation', async () => {
    const { fetcher, user } = start('/projects/default/settings', { signedIn: true })
    // General: name, read-only email, the one project; no storage line.
    const general = await screen.findByRole('tabpanel', { name: 'General' })
    expect(within(general).getByText('Ada Lovelace')).toBeTruthy()
    expect(within(general).getByText(ADA.email)).toBeTruthy()
    expect(within(general).getByText('Default project')).toBeTruthy()
    expect(within(general).queryByText('Storage')).toBeNull()
    await user.click(screen.getByRole('tab', { name: 'API key' }))
    const keys = within(screen.getByRole('table', { name: 'API keys' }))
    expect(keys.getAllByRole('columnheader').map(cell => cell.textContent)).toEqual(['Key prefix', 'Actions'])
    expect(keys.getByText(`${KEY_1.slice(0, 12)}…`)).toBeTruthy()
    // The snippet has a placeholder, never the truncated key; Copy copies the snippet.
    expect(screen.getByText(/AGENT_DEBUGGER_API_KEY=<your key>/)).toBeTruthy()
    expect(screen.queryByText(new RegExp(`AGENT_DEBUGGER_API_KEY=${KEY_1.slice(0, 12)}`))).toBeNull()
    const writeText = vi.fn(async () => {})
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    await user.click(screen.getByRole('button', { name: 'Copy .env for your agent' }))
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('AGENT_DEBUGGER_API_KEY=<your key>'))
    const rotateCalls = () => calls(fetcher).filter(call => call === 'POST /api/v1/auth/key/rotate')
    // Cancel: nothing sent.
    await user.click(screen.getByRole('button', { name: 'Rotate key' }))
    const confirm = screen.getByRole('group', { name: 'Rotate the API key?' })
    expect(confirm.textContent).toContain('The old key stops working immediately')
    await user.click(within(confirm).getByRole('button', { name: 'Cancel' }))
    expect(rotateCalls()).toHaveLength(0)
    // Confirm: one rotation, new key shown once.
    await user.click(screen.getByRole('button', { name: 'Rotate key' }))
    await user.click(within(screen.getByRole('group', { name: 'Rotate the API key?' })).getByRole('button', { name: 'Rotate key' }))
    expect(await screen.findByRole('heading', { name: 'Your API key' })).toBeTruthy()
    expect(rotateCalls()).toHaveLength(1)
    expect(screen.getByText(KEY_2)).toBeTruthy()
    expect(screen.getByRole('note').textContent).toContain('You won’t see this again')
    await user.click(screen.getByRole('button', { name: 'Done' }))
    expect(within(screen.getByRole('table', { name: 'API keys' })).getByText(`${KEY_2.slice(0, 12)}…`)).toBeTruthy()
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Rotate key' }))
    expect(screen.queryByText(KEY_2)).toBeNull()
    expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0)
  })

  it('has no Projects nav or Projects page in durable mode: project URLs go to the Dashboard', async () => {
    start('/projects', { signedIn: true })
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeTruthy()
    expect(window.location.hash).toBe('#/projects/default')
    const sidebar = within(screen.getByRole('complementary', { name: 'Project navigation' }))
    expect(sidebar.getByRole('link', { name: 'Tracing' })).toBeTruthy()
    expect(sidebar.queryByRole('link', { name: 'Projects' })).toBeNull()
    expect(screen.queryByRole('list', { name: 'Available projects' })).toBeNull()
    window.location.hash = '#/projects/new'
    await waitFor(() => expect(window.location.hash).toBe('#/projects/default'))
    expect(screen.queryByRole('button', { name: 'Create project' })).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Create project' })).toBeNull()
  })
})

describe('signed-in shell', () => {
  it.each(['/projects/default', '/projects/default/runs', '/projects/default/settings'])('never offers Sign in in the sidebar on %s', async path => {
    const { user } = start(path, { signedIn: true })
    // Wait for the project, so the shell is the final one (pages re-mount it once loaded).
    await screen.findByRole('link', { name: 'Default project' })
    const sidebar = screen.getByRole('complementary', { name: 'Project navigation' })
    const account = screen.getByLabelText('Account menu: Ada Lovelace')
    expect(within(sidebar).queryByRole('link', { name: /Sign in/ })).toBeNull()
    expect(within(sidebar).queryByText('Sign in')).toBeNull()
    // Name, theme and Sign out are in the footer menu only.
    const topbar = within(document.querySelector('.topbar'))
    expect(topbar.queryByText('Ada Lovelace')).toBeNull()
    expect(topbar.queryByRole('button', { name: /Sign out|Theme|Appearance/ })).toBeNull()
    expect(sidebar.contains(account)).toBe(true)
    await user.click(account)
    expect(within(await screen.findByRole('menu')).getByRole('menuitem', { name: 'Sign out' })).toBeTruthy()
  })

  it('switches the theme from the account menu with radio items and the keyboard', async () => {
    const { user } = start('/projects/default', { signedIn: true })
    await screen.findByRole('link', { name: 'Default project' })
    const account = screen.getByLabelText('Account menu: Ada Lovelace')
    await user.click(account)
    const themes = within(await screen.findByRole('group', { name: 'Theme' }))
    expect(themes.getAllByRole('menuitemradio').map(item => [item.textContent, item.getAttribute('aria-checked')])).toEqual([['Light', 'false'], ['Dark', 'false'], ['System', 'true']])
    await user.click(themes.getByRole('menuitemradio', { name: 'Dark' }))
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('agent-debugger.frontend.v1.theme')).toBe('dark')
    // The menu stays open, so the choice is visible; Escape closes it and returns focus.
    expect(themes.getByRole('menuitemradio', { name: 'Dark' }).getAttribute('aria-checked')).toBe('true')
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull())
    expect(document.activeElement).toBe(account)
    // Keyboard only: Enter opens, arrows move, Enter picks.
    await user.keyboard('{Enter}')
    await screen.findByRole('menu')
    const light = screen.getByRole('menuitemradio', { name: 'Light' })
    while (document.activeElement !== light) await user.keyboard('{ArrowDown}')
    await user.keyboard('{Enter}')
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem('agent-debugger.frontend.v1.theme')).toBe('light')
  })
})
