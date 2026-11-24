import { useEffect, useRef, useState } from 'react'
import Icon from '../components/Icon.jsx'
import CopyBlock from '../components/CopyBlock.jsx'
import ApiKeyReveal, { DURABLE_ENDPOINT } from '../features/access/ApiKeyReveal.jsx'
import { useAccount } from '../features/access/session.js'
import { expireSession, homeHref } from '../app/routes.jsx'
import './settings.css'

// The SDK's built-in local endpoint (sdk/python transport.LOCAL_ENDPOINT).
const LOCAL_ENDPOINT = 'http://127.0.0.1:8008/api/v1/local/traces'

const hours = seconds => Number.isFinite(seconds) && seconds > 0 ? `${+(seconds / 3600).toFixed(1)} h` : null

// Rotate: confirm first, then show the new key once. The old key stops working
// as soon as the backend answers; the new one lives only in this component.
function ApiKeySection({ account }) {
  const [step, setStep] = useState('idle'), [issued, setIssued] = useState(null), [error, setError] = useState('')
  const controller = useRef(null), confirmButton = useRef(null), rotateButton = useRef(null)
  useEffect(() => () => controller.current?.abort(), [])
  useEffect(() => { if (step === 'confirm') confirmButton.current?.focus() }, [step])
  async function rotate() {
    setStep('busy'); setError(''); controller.current = new AbortController()
    try {
      const { apiKey, keyPrefix } = await account.adapter.rotateKey({ signal: controller.current.signal })
      account.setUser({ ...account.user, keyPrefix })
      setIssued(apiKey); setStep('idle')
    } catch (err) {
      if (err?.name === 'AbortError') return
      if (err?.kind === 'expired') { expireSession(); return }
      setError('Could not rotate the key. The old key still works. Try again.'); setStep('idle')
    }
  }
  function done() { setIssued(null); setTimeout(() => rotateButton.current?.focus()) }
  return <section className="settings-card" aria-labelledby="settings-keys">
    <div className="settings-card-heading">
      <h2 id="settings-keys"><Icon name="key"/>API key</h2>
      {!issued && step !== 'confirm' && <button ref={rotateButton} type="button" className="button" disabled={step === 'busy'} onClick={() => setStep('confirm')}>{step === 'busy' ? 'Rotating…' : 'Rotate key'}</button>}
    </div>
    {issued ? <ApiKeyReveal apiKey={issued} Heading="h3" onContinue={done} continueLabel="Done"/> : <>
      <dl className="settings-facts"><div><dt>Current key</dt><dd><code>{account.user.keyPrefix}…</code></dd></div></dl>
      {step === 'confirm' && <div className="rotate-confirm" role="group" aria-labelledby="rotate-title" aria-describedby="rotate-description">
        <p id="rotate-title"><strong>Rotate the API key?</strong></p>
        <p id="rotate-description" className="settings-note">The old key stops working immediately. Agents that still send it get 401 until you give them the new key.</p>
        <div className="key-reveal-actions">
          <button ref={confirmButton} type="button" className="button solid" onClick={rotate}>Rotate key</button>
          <button type="button" className="button" onClick={() => { setStep('idle'); setTimeout(() => rotateButton.current?.focus()) }}>Cancel</button>
        </div>
      </div>}
      {error && <p className="form-error" role="alert">{error}</p>}
      <p className="settings-note">The SDK sends the key as a bearer token. Only its hash is stored, so a lost key cannot be shown again: rotate it instead.</p>
      <CopyBlock label=".env for your agent" text={`# A path ending in /api/v1/traces selects the durable exporter.\nAGENT_DEBUGGER_ENDPOINT=${DURABLE_ENDPOINT}\n# The key shown when you registered or last rotated it.\nAGENT_DEBUGGER_API_KEY=${account.user.keyPrefix}…`}/>
    </>}
  </section>
}

// Project settings. Durable: the account, its one project and its API key.
// Local: loopback capture with no accounts or keys.
export default function SettingsPage({ project }) {
  const account = useAccount()
  const retention = hours(project.retentionSeconds)
  const durable = project.storage === 'durable'
  return <section className="settings-page" aria-labelledby="settings-heading">
    <header className="view-heading"><h1 id="settings-heading">Settings</h1></header>
    {durable && account?.user && <section className="settings-card" aria-labelledby="settings-account">
      <h2 id="settings-account"><Icon name="user"/>Account</h2>
      <dl className="settings-facts">
        <div><dt>Name</dt><dd>{account.user.name}</dd></div>
        <div><dt>Email</dt><dd>{account.user.email}</dd></div>
        <div><dt>API key</dt><dd><code>{account.user.keyPrefix}…</code></dd></div>
      </dl>
    </section>}
    <section className="settings-card" aria-labelledby="settings-project">
      <h2 id="settings-project">Project</h2>
      <dl className="settings-facts">
        <div><dt>Name</dt><dd>{project.name}</dd></div>
        <div><dt>Project ID</dt><dd><code>{project.id}</code></dd></div>
        <div><dt>Storage</dt><dd>{durable ? 'ClickHouse, written by the trace-writer from Kafka. Traces stay after a backend restart.' : 'Temporary memory on the local backend. Restarting the backend clears every trace.'}</dd></div>
        {retention && <div><dt>Retention</dt><dd>Traces are kept for {retention}, then removed.</dd></div>}
      </dl>
    </section>
    {durable && account?.user ? <ApiKeySection account={account}/> : <section className="settings-card" aria-labelledby="settings-keys">
      <div className="settings-card-heading">
        <h2 id="settings-keys"><Icon name="key"/>API keys</h2>
        <button type="button" className="button" disabled aria-describedby="keys-unavailable">Create API key</button>
      </div>
      <p id="keys-unavailable" className="settings-note">Local mode does not use API keys. The backend accepts traces only from this computer (loopback) and only while it runs with <code>AGENT_DEBUGGER_LOCAL_MODE=1</code>.</p>
      <CopyBlock label=".env for your agent" text={`# Where the SDK sends traces. TraceSession.local() uses this address by default.\nAGENT_DEBUGGER_ENDPOINT=${LOCAL_ENDPOINT}\n# Set it to an empty value to turn export off.`}/>
      <p className="settings-note">Next: <a href={homeHref(project.id)}>Home</a> runs an example agent and confirms its trace arrives.</p>
    </section>}
  </section>
}
