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
  it('parses the landing page and docs slugs, and keeps the old default', () => {
    expect(parseRoute('#/')).toMatchObject({ landing: true, projectId: null })
    expect(parseRoute('#/docs')).toMatchObject({ docs: 'introduction', projectId: null })
    expect(parseRoute('#/docs/api')).toMatchObject({ docs: 'api', projectId: null })
    expect(parseRoute('')).toMatchObject({ path: '/projects', projectsPage: 'list' })
    expect(parseRoute('').landing).toBeUndefined()
  })

  it('renders the landing page signed out, without redirecting to sign in', async () => {
    const fetcher = start('/')
    expect(await screen.findByRole('heading', { level: 1, name: 'Find the step where your AI agent went wrong.' })).toBeTruthy()
    await settled(fetcher)
    // Signed out after the check, yet still on #/, not #/account/login.
    expect(within(screen.getByRole('banner')).getByRole('link', { name: 'Sign in' })).toBeTruthy()
    expect(window.location.hash).toBe('#/')
    expect(requested(fetcher)).toEqual(['GET /api/v1/auth/me'])
  })

  it('renders a docs page signed out, without redirecting to sign in', async () => {
    const fetcher = start('/docs/quickstart')
    expect(await screen.findByRole('heading', { level: 1, name: 'Quickstart' })).toBeTruthy()
    await settled(fetcher)
    expect(window.location.hash).toBe('#/docs/quickstart')
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

  it('shows Page not found for an unknown docs slug', async () => {
    start('/docs/no-such-page')
    expect(await screen.findByRole('heading', { level: 1, name: 'Page not found' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Start with the introduction' }).getAttribute('href')).toBe('#/docs')
  })

  it('links Docs in the app sidebar to the in-app docs', async () => {
    render(<FixtureApp/>)
    const docs = await screen.findByRole('link', { name: 'Docs' })
    expect(docs.getAttribute('href')).toBe('#/docs')
    expect(docs.getAttribute('target')).toBeNull()
  })
})
