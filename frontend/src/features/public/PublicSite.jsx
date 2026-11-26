import { useEffect } from 'react'
import Icon from '../../components/Icon.jsx'
import { Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger } from '../../components/ui/Menu.jsx'
import { useTheme } from '../../app/preferences.js'
import { accountHref } from '../../app/routes.jsx'
import LandingPage from './LandingPage.jsx'
import { DOCS, REPO_URL } from './site.js'
import './public.css'

function ThemeToggle({ dark, setPreference }) {
  const label = dark ? 'Switch to light theme' : 'Switch to dark theme'
  return <button type="button" className="button ghost icon-only" aria-label={label} title={label} onClick={() => setPreference(dark ? 'light' : 'dark')}><Icon name={dark ? 'sun' : 'moon'}/></button>
}

const External = ({ href, children }) => <a href={href} target="_blank" rel="noreferrer">{children}<span className="sr-only"> (opens in a new tab)</span></a>

// The public landing page. `signedIn` swaps Sign in / Sign up for one link to the
// dashboard; nothing here waits for the session check.
export default function PublicSite({ dashboard, signedIn }) {
  const theme = useTheme()
  const dark = theme.resolved === 'dark'
  useEffect(() => { document.title = 'Agent Debugger · Debug AI-agent runs from their traces' }, [])
  return <div className="public-site">
    <a className="skip-link" href="#public-main" onClick={event => { event.preventDefault(); document.getElementById('public-main')?.focus() }}>Skip to content</a>
    <header className="public-header">
      <div className="public-header-inner">
        <a className="public-brand" href="#/"><span className="brand-mark" aria-hidden="true"><Icon name="branch"/></span>Agent Debugger</a>
        <nav className="public-nav public-wide" aria-label="Site">
          <a href={DOCS.home}>Docs</a>
          <External href={REPO_URL}>GitHub</External>
        </nav>
        <div className="public-actions">
          <span className="public-wide"><ThemeToggle dark={dark} setPreference={theme.setPreference}/></span>
          {!signedIn && <a className="button ghost public-wide" href={accountHref('login')}>Sign in</a>}
          {signedIn
            ? <a className="button solid" href={dashboard}>Open dashboard<Icon name="arrow"/></a>
            : <a className="button solid" href={accountHref('register')}>Sign up</a>}
          {/* Under 640 px the site links, Sign in and the theme switch move into this menu. */}
          <Menu>
            <MenuTrigger><button type="button" className="button ghost icon-only public-narrow" aria-label="Menu"><Icon name="more"/></button></MenuTrigger>
            <MenuContent align="end" className="public-menu">
              <MenuItem asChild><a href={DOCS.home}>Docs</a></MenuItem>
              <MenuItem asChild><a href={REPO_URL} target="_blank" rel="noreferrer">GitHub<span className="sr-only"> (opens in a new tab)</span></a></MenuItem>
              {!signedIn && <MenuItem asChild><a href={accountHref('login')}>Sign in</a></MenuItem>}
              <MenuSeparator/>
              <MenuItem onSelect={() => theme.setPreference(dark ? 'light' : 'dark')}><Icon name={dark ? 'sun' : 'moon'}/>{dark ? 'Light theme' : 'Dark theme'}</MenuItem>
            </MenuContent>
          </Menu>
        </div>
      </div>
    </header>
    <main id="public-main" tabIndex="-1" className="public-main">
      <LandingPage signedIn={signedIn} dashboard={dashboard} theme={dark ? 'dark' : 'light'}/>
    </main>
    <footer className="public-footer">
      <div className="public-footer-inner">
        <div className="public-footer-brand">
          <a className="public-brand" href="#/"><span className="brand-mark" aria-hidden="true"><Icon name="branch"/></span>Agent Debugger</a>
          <p>Debug AI-agent runs from their OpenTelemetry traces.</p>
        </div>
        <nav className="public-footer-columns" aria-label="Footer">
          <div>
            <h2>Product</h2>
            <ul>
              {signedIn
                ? <li><a href={dashboard}>Open dashboard</a></li>
                : <><li><a href={accountHref('register')}>Sign up</a></li><li><a href={accountHref('login')}>Sign in</a></li></>}
              <li><a href={DOCS.limits}>Limits and roadmap</a></li>
            </ul>
          </div>
          <div>
            <h2>Docs</h2>
            <ul>
              <li><a href={DOCS.quickstart}>Quickstart</a></li>
              <li><a href={DOCS.traceSession}>Python SDK</a></li>
              <li><a href={DOCS.ingestApi}>HTTP API</a></li>
              <li><a href={DOCS.selfHosting}>Self-hosting</a></li>
            </ul>
          </div>
          <div>
            <h2>Resources</h2>
            <ul>
              <li><External href={REPO_URL}>GitHub</External></li>
              <li><a href={DOCS.runsAndSpans}>Runs and spans</a></li>
              <li><a href={DOCS.retries}>Errors and retries</a></li>
            </ul>
          </div>
        </nav>
      </div>
    </footer>
  </div>
}
