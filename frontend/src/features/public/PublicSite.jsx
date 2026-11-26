import { useEffect } from 'react'
import Icon from '../../components/Icon.jsx'
import { useTheme } from '../../app/preferences.js'
import { accountHref, docsHref } from '../../app/routes.jsx'
import LandingPage from './LandingPage.jsx'
import DocsPage from './DocsPage.jsx'
import { REPO_URL } from './site.js'
import './public.css'

const next = ['light', 'dark']
function ThemeToggle() {
  const theme = useTheme()
  const dark = theme.resolved === 'dark'
  const label = dark ? 'Switch to light theme' : 'Switch to dark theme'
  return <button type="button" className="button ghost icon-only" aria-label={label} title={label} onClick={() => theme.setPreference(next[dark ? 0 : 1])}><Icon name={dark ? 'sun' : 'moon'}/></button>
}

// Landing and docs share this header and footer. `signedIn` swaps Sign in / Sign up
// for one link to the dashboard; nothing here waits for the session check.
export default function PublicSite({ route, dashboard, signedIn }) {
  const docs = !!route.docs
  useEffect(() => { if (!docs) document.title = 'Agent Debugger · Debug AI-agent runs from their traces' }, [docs])
  return <div className="public-site" data-page={docs ? 'docs' : 'landing'}>
    <a className="skip-link" href="#public-main" onClick={event => { event.preventDefault(); document.getElementById('public-main')?.focus() }}>Skip to content</a>
    <header className="public-header">
      <div className="public-header-inner">
        <a className="public-brand" href="#/"><span className="brand-mark" aria-hidden="true"><Icon name="branch"/></span>Agent Debugger</a>
        <nav className="public-nav" aria-label="Site">
          <a href={docsHref()} aria-current={docs ? 'page' : undefined}>Docs</a>
          <a href={REPO_URL} target="_blank" rel="noreferrer">GitHub<span className="sr-only"> (opens in a new tab)</span></a>
        </nav>
        <div className="public-actions">
          <ThemeToggle/>
          {signedIn
            ? <a className="button solid" href={dashboard}>Open dashboard<Icon name="arrow"/></a>
            : <><a className="button ghost" href={accountHref('login')}>Sign in</a><a className="button solid" href={accountHref('register')}>Sign up</a></>}
        </div>
      </div>
    </header>
    <main id="public-main" tabIndex="-1" className="public-main">
      {docs ? <DocsPage page={route.docs}/> : <LandingPage signedIn={signedIn} dashboard={dashboard}/>}
    </main>
    <footer className="public-footer">
      <div className="public-footer-inner">
        <span>Agent Debugger · an OJT software engineering project</span>
        <nav aria-label="Footer">
          <a href={docsHref()}>Docs</a>
          <a href={docsHref('quickstart')}>Quickstart</a>
          <a href={docsHref('api')}>HTTP API</a>
          <a href={REPO_URL} target="_blank" rel="noreferrer">GitHub<span className="sr-only"> (opens in a new tab)</span></a>
        </nav>
      </div>
    </footer>
  </div>
}
