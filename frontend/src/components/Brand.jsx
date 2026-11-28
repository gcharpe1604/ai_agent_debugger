import { useTheme } from '../app/preferences.js'
import '../styles/chrome.css'

// The "▸ agent-debugger" mono wordmark (landing, auth pages, app sidebar; the docs
// site renders the same markup in docs-site/src/components/SiteTitle.astro).
export function Wordmark({ href = '#/', label }) {
  return <a className="adbg-wordmark" href={href} aria-label={label}>
    <span className="adbg-mark" aria-hidden="true">▸</span><span className="adbg-wordmark-text">agent-debugger</span>
  </a>
}

// Light / dark pill. The stored preference defaults to "system"; a click stores the
// other resolved theme under the same key the docs site reads
// (agent-debugger.frontend.v1.theme), so the choice carries between app and docs.
export function ThemeToggle() {
  const { resolved, setPreference } = useTheme()
  const dark = resolved === 'dark'
  const label = dark ? 'Switch to light theme' : 'Switch to dark theme'
  return <button type="button" className="adbg-theme" aria-label={label} title={label} onClick={() => setPreference(dark ? 'light' : 'dark')}>
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" strokeWidth="1.5"/><path d="M8 1.75a6.25 6.25 0 0 1 0 12.5z" fill="currentColor"/></svg>
    <span className="adbg-theme-name" aria-hidden="true">{dark ? 'dark' : 'light'}</span>
  </button>
}
