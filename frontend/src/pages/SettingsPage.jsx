import { useState } from 'react'
import Icon from '../components/Icon.jsx'
import { homeHref } from '../app/routes.jsx'
import './settings.css'

// The SDK's built-in local endpoint (sdk/python transport.LOCAL_ENDPOINT).
const LOCAL_ENDPOINT = 'http://127.0.0.1:8008/api/v1/local/traces'

function CopyBlock({ label, text }) {
  const [notice, setNotice] = useState('')
  async function copy() {
    try { await navigator.clipboard.writeText(text); setNotice(`${label} copied`) }
    catch { setNotice('Clipboard unavailable. Select the text and copy it.') }
  }
  return <div className="copy-block">
    <div className="copy-block-header"><span>{label}</span><button type="button" className="button small" onClick={copy}><Icon name="copy"/>Copy</button></div>
    <pre><code>{text}</code></pre>
    <span className="sr-only" aria-live="polite">{notice}</span>
  </div>
}

const hours = seconds => Number.isFinite(seconds) && seconds > 0 ? `${+(seconds / 3600).toFixed(1)} h` : null

// Local workspace settings. Local capture has no accounts or keys: it accepts
// loopback traffic only. Project API keys arrive with durable ingestion.
export default function SettingsPage({ project }) {
  const retention = hours(project.retentionSeconds)
  return <section className="settings-page" aria-labelledby="settings-heading">
    <header className="view-heading"><h1 id="settings-heading">Settings</h1><span className="secondary">Project details and how agents send traces to it.</span></header>
    <section className="settings-card" aria-labelledby="settings-project">
      <h2 id="settings-project">Project</h2>
      <dl className="settings-facts">
        <div><dt>Name</dt><dd>{project.name}</dd></div>
        <div><dt>Project ID</dt><dd><code>{project.id}</code></dd></div>
        <div><dt>Storage</dt><dd>Temporary memory on the local backend. Restarting the backend clears every trace.</dd></div>
        {retention && <div><dt>Retention</dt><dd>Traces are kept for {retention}, then removed.</dd></div>}
      </dl>
    </section>
    <section className="settings-card" aria-labelledby="settings-keys">
      <div className="settings-card-heading">
        <h2 id="settings-keys"><Icon name="key"/>API keys</h2>
        <button type="button" className="button" disabled aria-describedby="keys-unavailable">Create API key</button>
      </div>
      <p id="keys-unavailable" className="settings-note">Local mode does not use API keys. The backend accepts traces only from this computer (loopback) and only while it runs with <code>AGENT_DEBUGGER_LOCAL_MODE=1</code>. Project API keys come with durable ingestion.</p>
      <CopyBlock label=".env for your agent" text={`# Where the SDK sends traces. TraceSession.local() uses this address by default.\nAGENT_DEBUGGER_ENDPOINT=${LOCAL_ENDPOINT}\n# Set it to an empty value to turn export off.`}/>
      <p className="settings-note">Next: <a href={homeHref(project.id)}>Home</a> runs an example agent and confirms its trace arrives.</p>
    </section>
  </section>
}
