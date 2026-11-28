import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import App from '../../app/App.jsx'
import FixtureApp from '../../test/FixtureApp.jsx'
import { createApiAdapters } from '../../data/apiRepository.js'
import { expireSession, parseRoute } from '../../app/routes.jsx'
import { DOCS_PAGES } from './docsPages.js'
import { SDK_INSTALL, envSnippet, traceSessionSnippet } from './site.js'

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
    expect(await screen.findByRole('heading', { level: 1, name: 'Debug AI agents from the trace, not the logs.' })).toBeTruthy()
    await settled(fetcher)
    // Signed out after the check, yet still on #/, not #/account/login.
    const header = within(screen.getByRole('banner'))
    expect(header.getByRole('link', { name: 'Sign in' })).toBeTruthy()
    expect(header.getByRole('link', { name: 'Sign up' })).toBeTruthy()
    expect(header.queryByRole('link', { name: 'Open dashboard' })).toBeNull()
    expect(window.location.hash).toBe('#/')
    expect(requested(fetcher)).toEqual(['GET /api/v1/auth/me'])
  })

  it('shows Open dashboard in the header, hero and final call to action when signed in', async () => {
    start('/', { signedIn: true })
    const header = within(await screen.findByRole('banner'))
    const link = await header.findByRole('link', { name: 'Open dashboard' })
    expect(link.getAttribute('href')).toBe('#/projects/default')
    expect(header.queryByRole('link', { name: 'Sign in' })).toBeNull()
    expect(header.queryByRole('link', { name: 'Sign up' })).toBeNull()
    const main = within(screen.getByRole('main'))
    expect(main.getAllByRole('link', { name: 'Open dashboard' })).toHaveLength(2)
    expect(main.queryByRole('link', { name: 'Sign up' })).toBeNull()
  })

  it('links every docs link to a page of the docs site', async () => {
    start('/')
    await screen.findByRole('heading', { level: 1 })
    expect(within(screen.getByRole('banner')).getByRole('link', { name: 'Docs' }).getAttribute('href')).toBe('/docs/')
    const internal = screen.getAllByRole('link').map(link => link.getAttribute('href')).filter(href => !href.startsWith('#') && !href.startsWith('https://github.com/'))
    expect(internal.length).toBeGreaterThan(5)
    for (const href of internal) {
      expect(href.startsWith('/docs/')).toBe(true)
      expect(DOCS_PAGES).toContain(href.slice('/docs/'.length))
    }
    const footer = within(screen.getByRole('navigation', { name: 'Footer' }))
    const targets = Object.fromEntries(footer.getAllByRole('link').map(link => [link.textContent.replace(' (opens in a new tab)', ''), link.getAttribute('href')]))
    expect(targets).toEqual({
      'Sign up': '#/account/register?returnTo=%2Fprojects', 'Sign in': '#/account/login?returnTo=%2Fprojects', Dashboard: '/docs/product/dashboard/',
      Quickstart: '/docs/get-started/quickstart/', TraceSession: '/docs/sdk/trace-session/', 'Errors and retries': '/docs/concepts/errors-and-retries/', 'Ingest API': '/docs/api/ingest/',
      GitHub: 'https://github.com/gcharpe1604/ai_agent_debugger', 'Self-hosting': '/docs/self-hosting/docker-compose/', Limits: '/docs/limits/',
    })
    expect(document.body.textContent).not.toMatch(/\bOJT\b/)
    // Footer column titles are labels, not headings.
    expect(within(screen.getByRole('contentinfo')).queryAllByRole('heading')).toHaveLength(0)
    expect([...document.querySelectorAll('.adbg-footer-columns .adbg-label')].map(label => [label.tagName, label.textContent])).toEqual([['P', 'Product'], ['P', 'Docs'], ['P', 'Resources']])
  })

  it('shows the screenshots of the resolved theme, with alt text and file sizes', async () => {
    localStorage.setItem('agent-debugger.frontend.v1.theme', 'dark')
    start('/')
    const hero = await screen.findByRole('img', { name: /^Trace view of a failed live tool-task-agent run/ })
    expect(hero.getAttribute('src')).toBe('/landing/hero-dark.webp')
    const sources = screen.getAllByRole('img').map(image => image.getAttribute('src'))
    expect(sources).toEqual(['hero', 'failed', 'tree', 'inspector', 'dashboard'].map(name => `/landing/${name}-dark.webp`))
    // Only the resolved theme's files are referenced, so the other set never downloads.
    expect(document.documentElement.innerHTML).not.toContain('-light.webp')
    expect(document.querySelectorAll('picture, source, link[rel="preload"][as="image"]')).toHaveLength(0)
    await act(async () => { within(screen.getByRole('banner')).getByRole('button', { name: 'Switch to light theme' }).click() })
    expect(hero.getAttribute('src')).toBe('/landing/hero-light.webp')
    expect(document.documentElement.innerHTML).not.toContain('-dark.webp')
    expect(screen.getAllByRole('img').map(image => [image.getAttribute('width'), image.getAttribute('height')])).toEqual([
      ['2400', '1034'], ['1568', '1002'], ['1390', '654'], ['1008', '1084'], ['1520', '1494'],
    ])
    for (const image of screen.getAllByRole('img')) expect(image.getAttribute('alt').length).toBeGreaterThan(60)
    // One h1; the section labels are paragraphs, the section titles h2.
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(within(screen.getByRole('main')).getAllByRole('heading', { level: 2 }).map(heading => heading.textContent)).toEqual([
      'Instrument in minutes', 'Find failed runs across agents', 'See the whole run', 'Read the failing step', 'Watch error rate and latency', 'The span path', 'Trace your first run.',
    ])
    expect([...document.querySelectorAll('.lp-row-label')].map(label => [label.tagName, label.textContent])).toEqual([
      ['P', '01 · Quickstart'], ['P', '02 · Runs'], ['P', '03 · Trace'], ['P', '04 · Inspector'], ['P', '05 · Dashboard'], ['P', '06 · Architecture'],
    ])
    expect(within(screen.getByRole('region', { name: 'Trace your first run.' })).queryByRole('img')).toBeNull()
  })

  it('labels the failed run, the span types and the recovered retry in text, not colour alone', async () => {
    start('/')
    const caption = (await screen.findByRole('img', { name: /^Trace view/ })).closest('figure').querySelector('figcaption')
    expect(caption.textContent).toContain('● failed')
    expect(caption.textContent).toContain('tool-task-agent')
    const trace = within(screen.getByRole('region', { name: 'See the whole run' }))
    expect(within(trace.getByRole('list', { name: 'Span types' })).getAllByRole('listitem').map(item => item.textContent)).toEqual(['agent', 'model', 'tool', 'retrieval'])
    expect(trace.getByText(/is a recovered retry, not a failed run\./)).toBeTruthy()
  })

  it('draws the write and read paths into one ClickHouse, with PostgreSQL beside the API', async () => {
    start('/')
    const section = within(await screen.findByRole('region', { name: 'The span path' }))
    const items = name => within(section.getByRole('list', { name })).getAllByRole('listitem').map(item => item.textContent)
    expect(items('Write path')).toEqual([
      'Agent + SDKTraceSession', 'HTTPS · Bearer API key', 'Ingest API/api/v1/traces', 'publish', 'Kafkaagentdbg.traces.v1',
      'consume', 'Trace writerKafka consumer', 'insert', 'ClickHousetelemetry_spans',
    ])
    // The Web UI reads through the API, never ClickHouse directly.
    expect(items('Read path')).toEqual(['Web UIReact', 'session cookie', 'Read API/api/v1/projects/…', 'SQL', 'ClickHousethe same node as above'])
    expect(items('Accounts')).toEqual([
      'Ingest API + Read APIthe same app as above', 'user lookup: key hash, session user_id', 'PostgreSQLAccounts and API key hashes. Spans never go here.',
    ])
    const notes = [...screen.getByRole('region', { name: 'The span path' }).querySelectorAll('.lp-arch-notes > div')].map(note => [note.querySelector('dt').textContent, note.querySelector('dd').textContent])
    expect(notes).toEqual([
      ['Kafka', 'The agent never waits on ClickHouse; a writer restart loses nothing.'],
      ['ClickHouse', 'Column store for time-range scans of spans.'],
      ['PostgreSQL', 'Accounts need updates and unique emails; spans are append-only, so they live in ClickHouse.'],
    ])
  })

  it('puts Docs, GitHub and Sign in in the header menu; the theme switch stays in the header', async () => {
    start('/')
    const header = within(await screen.findByRole('banner'))
    expect(header.getByRole('link', { name: 'Sign up' })).toBeTruthy()
    expect(header.getByRole('button', { name: 'Switch to dark theme' })).toBeTruthy()
    const menu = header.getByRole('button', { name: 'Menu' })
    await act(async () => { menu.focus(); menu.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })) })
    const items = await screen.findAllByRole('menuitem')
    expect(items.map(item => item.textContent)).toEqual(['Docs', 'GitHub (opens in a new tab)', 'Sign in'])
    expect(items[0].getAttribute('href')).toBe('/docs/')
  })

  it('renders the setup tabs from the site constants and copies the raw text', async () => {
    const writeText = vi.fn(async () => {})
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    start('/')
    const tabs = await screen.findAllByRole('tab')
    expect(tabs.map(tab => tab.textContent)).toEqual(['terminal', '.env', 'agent.py'])
    expect(tabs[0].getAttribute('aria-selected')).toBe('true')
    const panelText = () => [...screen.getByRole('tabpanel').querySelectorAll('.lp-lt')].map(line => line.textContent).join('\n')
    expect(panelText()).toBe(SDK_INSTALL)
    // The install command may break after '/', '#' and '='; the copy is the constant.
    expect(screen.getByRole('tabpanel').querySelectorAll('wbr').length).toBeGreaterThan(5)
    await act(async () => { screen.getByRole('button', { name: 'Copy terminal' }).click() })
    expect(writeText).toHaveBeenLastCalledWith(SDK_INSTALL)

    // Arrow keys move between tabs (roving focus); the tab follows focus.
    await act(async () => { tabs[0].focus(); fireEvent.keyDown(tabs[0], { key: 'ArrowRight' }) })
    await waitFor(() => expect(document.activeElement).toBe(tabs[1]))
    await waitFor(() => expect(tabs[1].getAttribute('aria-selected')).toBe('true'))
    expect(panelText()).toBe(envSnippet())
    expect(envSnippet()).toMatch(/^AGENT_DEBUGGER_ENDPOINT=http:\/\/localhost(:\d+)?\/api\/v1\/traces\n/)
    await act(async () => { screen.getByRole('button', { name: 'Copy .env' }).click() })
    expect(writeText).toHaveBeenLastCalledWith(envSnippet())

    await act(async () => { fireEvent.keyDown(tabs[1], { key: 'ArrowRight' }) })
    await waitFor(() => expect(document.activeElement).toBe(tabs[2]))
    await waitFor(() => expect(tabs[2].getAttribute('aria-selected')).toBe('true'))
    expect(panelText()).toBe(traceSessionSnippet)
    await act(async () => { screen.getByRole('button', { name: 'Copy agent.py' }).click() })
    expect(writeText).toHaveBeenLastCalledWith(traceSessionSnippet)

    const install = screen.getByRole('button', { name: 'Copy install command' })
    expect(install.parentElement.querySelector('code').textContent).toBe(SDK_INSTALL)
    await act(async () => { install.click() })
    expect(writeText).toHaveBeenLastCalledWith(SDK_INSTALL)
  })

  it('keeps the agent.py snippet to the SDK API and the terminal tab\'s install line', () => {
    // Only the SDK is installed by the terminal tab, so the snippet imports nothing else.
    expect(traceSessionSnippet.match(/^(?:from|import) .+$/gm)).toEqual(['from ai_agent_debugger_sdk import TraceSession'])
    expect(traceSessionSnippet).toContain('tracing.instrument(')
    expect(traceSessionSnippet).toContain('payloads={"search": (')
    expect(traceSessionSnippet).toContain('tracing.operation("agent", "MyAgent.run")')
    expect(SDK_INSTALL).toBe('pip install "git+https://github.com/gcharpe1604/ai_agent_debugger.git#subdirectory=sdk/python"')
  })

  it('links Docs in the app sidebar to the docs site', async () => {
    render(<FixtureApp/>)
    const docs = await screen.findByRole('link', { name: 'Docs' })
    expect(docs.getAttribute('href')).toBe('/docs/')
    expect(docs.getAttribute('target')).toBeNull()
  })
})
