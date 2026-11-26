import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import App from '../../app/App.jsx'
import FixtureApp from '../../test/FixtureApp.jsx'
import { createApiAdapters } from '../../data/apiRepository.js'
import { expireSession, parseRoute } from '../../app/routes.jsx'

const ADA = { id: '6f1c0d52-0000-4000-8000-000000000001', name: 'Ada Lovelace', email: 'ada@example.com', key_prefix: 'adbg_sk_AAAA' }
const json = (status, body) => ({ ok: status >= 200 && status < 300, status, json: async () => body })

// The durable backend, reduced to the session check: a public page must not read anything else.
function start(path, { signedIn = false } = {}) {
  window.history.replaceState(null, '', '/#' + path)
  const fetcher = vi.fn(async (url, init = {}) => {
    if ((init.method || 'GET') === 'GET' && url === '/api/v1/auth/me') return signedIn ? json(200, ADA) : json(401, { detail: 'Not authenticated' })
    throw new Error(`unexpected request ${url}`)
  })
  render(<App {...createApiAdapters(fetcher, { source: 'durable', onUnauthorized: () => expireSession() })}/>)
  return fetcher
}
// Waits until the session check has answered and React has applied it, so a
// redirect to sign in (if any) has had its chance to run.
async function settled(fetcher) {
  await waitFor(() => expect(fetcher).toHaveBeenCalled())
  await act(async () => { await fetcher.mock.results[0].value; await new Promise(resolve => setTimeout(resolve, 20)) })
}
const requested = fetcher => fetcher.mock.calls.map(([url, init]) => `${init?.method || 'GET'} ${url}`)

beforeEach(() => { vi.spyOn(window, 'scrollTo').mockImplementation(() => {}) })

describe('public routes', () => {
  it('parses the landing page and keeps the old default; #/docs is no longer a route', () => {
    expect(parseRoute('#/')).toMatchObject({ landing: true, projectId: null })
    expect(parseRoute('')).toMatchObject({ path: '/projects', projectsPage: 'list' })
    expect(parseRoute('').landing).toBeUndefined()
    expect(parseRoute('#/docs').landing).toBeUndefined()
    expect(parseRoute('#/docs').docs).toBeUndefined()
  })

  it('renders the landing page signed out, without redirecting to sign in', async () => {
    const fetcher = start('/')
    expect(await screen.findByRole('heading', { level: 1, name: 'Find the step where your AI agent went wrong.' })).toBeTruthy()
    await settled(fetcher)
    // Signed out after the check, yet still on #/, not #/account/login.
    const header = within(screen.getByRole('banner'))
    expect(header.getByRole('link', { name: 'Sign in' })).toBeTruthy()
    expect(header.getByRole('link', { name: 'Sign up' })).toBeTruthy()
    expect(window.location.hash).toBe('#/')
    expect(requested(fetcher)).toEqual(['GET /api/v1/auth/me'])
  })

  it('shows Open dashboard in the header when signed in', async () => {
    start('/', { signedIn: true })
    const header = within(await screen.findByRole('banner'))
    const link = await header.findByRole('link', { name: 'Open dashboard' })
    expect(link.getAttribute('href')).toBe('#/projects/default')
    expect(header.queryByRole('link', { name: 'Sign in' })).toBeNull()
    expect(header.queryByRole('link', { name: 'Sign up' })).toBeNull()
  })

  it('links every docs link to the docs site on the same origin', async () => {
    start('/')
    await screen.findByRole('heading', { level: 1 })
    expect(within(screen.getByRole('banner')).getByRole('link', { name: 'Docs' }).getAttribute('href')).toBe('/docs/')
    const internal = screen.getAllByRole('link').map(link => link.getAttribute('href')).filter(href => !href.startsWith('#') && !href.startsWith('https://github.com/'))
    expect(internal.length).toBeGreaterThan(5)
    for (const href of internal) expect(href).toMatch(/^\/docs\/([a-z0-9-]+\/)*$/)
    expect(screen.getByRole('link', { name: 'Self-host it on one VM' }).getAttribute('href')).toBe('/docs/self-hosting/docker-compose/')
    expect(document.body.textContent).not.toMatch(/\bOJT\b/)
  })

  it('shows the screenshots of the resolved theme, with alt text', async () => {
    localStorage.setItem('agent-debugger.frontend.v1.theme', 'dark')
    start('/')
    const hero = await screen.findByRole('img', { name: /^Trace view of a failed tool-task-agent run/ })
    expect(hero.getAttribute('src')).toBe('/landing/trace-dark.webp')
    const sources = screen.getAllByRole('img').map(image => image.getAttribute('src'))
    expect(sources).toEqual(['/landing/trace-dark.webp', '/landing/tracing-failed-dark.webp', '/landing/trace-dark.webp', '/landing/trace-dark.webp', '/landing/dashboard-dark.webp'])
    await act(async () => { within(screen.getByRole('banner')).getByRole('button', { name: 'Switch to light theme' }).click() })
    expect(hero.getAttribute('src')).toBe('/landing/trace-light.webp')
    expect(screen.getAllByRole('img').every(image => image.getAttribute('alt').length > 40)).toBe(true)
  })

  it('switches the code example tabs', async () => {
    start('/')
    const tab = await screen.findByRole('tab', { name: '.env' })
    expect(screen.getByRole('tab', { name: 'TraceSession', selected: true })).toBeTruthy()
    await act(async () => { tab.focus(); tab.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0 })) })
    expect(await screen.findByText(/AGENT_DEBUGGER_ENDPOINT=http:\/\/localhost(:\d+)?\/api\/v1\/traces/)).toBeTruthy()
  })

  it('links Docs in the app sidebar to the docs site', async () => {
    render(<FixtureApp/>)
    const docs = await screen.findByRole('link', { name: 'Docs' })
    expect(docs.getAttribute('href')).toBe('/docs/')
    expect(docs.getAttribute('target')).toBeNull()
  })
})
