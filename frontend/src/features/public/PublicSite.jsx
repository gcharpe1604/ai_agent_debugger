import { useEffect } from 'react'
import { Menu, MenuContent, MenuItem, MenuTrigger } from '../../components/ui/Menu.jsx'
import { useTheme } from '../../app/preferences.js'
import { accountHref } from '../../app/routes.jsx'
import LandingPage from './LandingPage.jsx'
import { DOCS, REPO_URL } from './site.js'
import './public.css'

export const Wordmark = () => <a className="lp-wordmark" href="#/"><span className="lp-mark" aria-hidden="true">▸</span><span className="lp-wordmark-text">agent-debugger</span></a>

// Half-filled circle; the theme name sits next to it from 768 px up.
function ThemeToggle({ dark, setPreference }) {
  const label = dark ? 'Switch to light theme' : 'Switch to dark theme'
  return <button type="button" className="lp-theme" aria-label={label} title={label} onClick={() => setPreference(dark ? 'light' : 'dark')}>
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" strokeWidth="1.5"/><path d="M8 1.75a6.25 6.25 0 0 1 0 12.5z" fill="currentColor"/></svg>
    <span className="lp-theme-name" aria-hidden="true">{dark ? 'dark' : 'light'}</span>
  </button>
}

const External = ({ href, children }) => <a href={href} target="_blank" rel="noreferrer">{children}<span className="sr-only"> (opens in a new tab)</span></a>

// The public landing page. `signedIn` swaps Sign in / Sign up for one link to the
// dashboard; nothing here waits for the session check.
export default function PublicSite({ dashboard, signedIn }) {
  const theme = useTheme()
  const dark = theme.resolved === 'dark'
  useEffect(() => { document.title = 'agent-debugger · Debug AI agents from the trace' }, [])
  return <div className="public-site">
    <a className="skip-link" href="#public-main" onClick={event => { event.preventDefault(); document.getElementById('public-main')?.focus() }}>Skip to content</a>
    <header className="lp-nav">
      <div className="lp-container lp-nav-inner">
        <Wordmark/>
        <nav className="lp-nav-links lp-wide" aria-label="Site">
          <a href={DOCS.home}>Docs</a>
          <External href={REPO_URL}>GitHub</External>
        </nav>
        <div className="lp-nav-actions">
          <ThemeToggle dark={dark} setPreference={theme.setPreference}/>
          {signedIn
            ? <a className="lp-btn lp-btn-primary lp-btn-sm" href={dashboard} aria-label="Open dashboard"><span className="lp-wide">Open dashboard</span><span className="lp-narrow">Dashboard</span></a>
            : <>
              <a className="lp-nav-signin lp-wide" href={accountHref('login')}>Sign in</a>
              <a className="lp-btn lp-btn-primary lp-btn-sm" href={accountHref('register')}>Sign up</a>
            </>}
          {/* Under 768 px Docs, GitHub and Sign in move into this menu. */}
          <Menu>
            <MenuTrigger><button type="button" className="lp-menu-button lp-narrow" aria-label="Menu">
              <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
            </button></MenuTrigger>
            <MenuContent align="end" className="public-menu">
              <MenuItem asChild><a href={DOCS.home}>Docs</a></MenuItem>
              <MenuItem asChild><a href={REPO_URL} target="_blank" rel="noreferrer">GitHub<span className="sr-only"> (opens in a new tab)</span></a></MenuItem>
              {!signedIn && <MenuItem asChild><a href={accountHref('login')}>Sign in</a></MenuItem>}
            </MenuContent>
          </Menu>
        </div>
      </div>
    </header>
    <main id="public-main" tabIndex="-1" className="public-main">
      <LandingPage signedIn={signedIn} dashboard={dashboard} theme={dark ? 'dark' : 'light'}/>
    </main>
    <footer className="lp-footer">
      <div className="lp-container lp-row">
        <div className="lp-footer-brand"><Wordmark/><p>© 2026</p></div>
        <nav className="lp-footer-columns" aria-label="Footer">
          <div>
            <p className="lp-label">Product</p>
            <ul>
              {signedIn
                ? <li><a href={dashboard}>Open dashboard</a></li>
                : <><li><a href={accountHref('register')}>Sign up</a></li><li><a href={accountHref('login')}>Sign in</a></li></>}
              <li><a href={DOCS.dashboard}>Dashboard</a></li>
            </ul>
          </div>
          <div>
            <p className="lp-label">Docs</p>
            <ul>
              <li><a href={DOCS.quickstart}>Quickstart</a></li>
              <li><a href={DOCS.traceSession}>TraceSession</a></li>
              <li><a href={DOCS.retries}>Errors and retries</a></li>
              <li><a href={DOCS.ingestApi}>Ingest API</a></li>
            </ul>
          </div>
          <div>
            <p className="lp-label">Resources</p>
            <ul>
              <li><External href={REPO_URL}>GitHub</External></li>
              <li><a href={DOCS.selfHosting}>Self-hosting</a></li>
              <li><a href={DOCS.limits}>Limits</a></li>
            </ul>
          </div>
        </nav>
      </div>
    </footer>
  </div>
}
