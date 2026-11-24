import { useEffect, useRef, useState } from 'react'
import CopyBlock from '../components/CopyBlock.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/Tabs.jsx'
import Timestamp from '../components/Timestamp.jsx'
import ApiKeyReveal, { DURABLE_ENDPOINT } from '../features/access/ApiKeyReveal.jsx'
import { useAccount } from '../features/access/session.js'
import { expireSession, homeHref } from '../app/routes.jsx'
import './settings.css'

// The SDK's built-in local endpoint (sdk/python transport.LOCAL_ENDPOINT).
const LOCAL_ENDPOINT = 'http://127.0.0.1:8008/api/v1/local/traces'
// The snippet never contains the key: the full key is shown once only, and a
// prefix would not work if pasted.
const DURABLE_SNIPPET = `# A path ending in /api/v1/traces selects the durable exporter.\nAGENT_DEBUGGER_ENDPOINT=${DURABLE_ENDPOINT}\n# The key shown when you registered or last rotated it.\nAGENT_DEBUGGER_API_KEY=<your key>`

const hours = seconds => Number.isFinite(seconds) && seconds > 0 ? `${+(seconds / 3600).toFixed(1)} h` : null

// Rotate: confirm first, then show the new key once. The old key stops working
// as soon as the backend answers; the new one lives only in this component.
function ApiKeyTab({ account }) {
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
  const created = account.user.createdAt
  if (issued) return <ApiKeyReveal apiKey={issued} Heading="h3" onContinue={done} continueLabel="Done"/>
  return <>
    <table className="settings-table" aria-label="API keys">
      <thead><tr><th scope="col">Key prefix</th>{created && <th scope="col">Created</th>}<th scope="col" className="settings-actions-cell">Actions</th></tr></thead>
      <tbody><tr>
        <td><code>{account.user.keyPrefix}…</code></td>
        {created && <td><Timestamp value={created}/></td>}
        <td className="settings-actions-cell"><button ref={rotateButton} type="button" className="button small" disabled={step !== 'idle'} onClick={() => setStep('confirm')}>{step === 'busy' ? 'Rotating…' : 'Rotate key'}</button></td>
      </tr></tbody>
    </table>
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
    <CopyBlock label=".env for your agent" text={DURABLE_SNIPPET}/>
  </>
}

function Facts({ rows }) {
  return <dl className="settings-facts">{rows.filter(Boolean).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
}

// Settings: General (account and project) and API key. Local mode has no
// accounts or keys; its API key tab explains the loopback endpoint instead.
export default function SettingsPage({ project }) {
  const account = useAccount()
  const [tab, setTab] = useState('general')
  const retention = hours(project.retentionSeconds)
  const signedIn = project.storage === 'durable' && account?.user
  return <section className="settings-page" aria-labelledby="settings-heading">
    <header className="view-heading"><h1 id="settings-heading">Settings</h1></header>
    <Tabs value={tab} onValueChange={setTab} className="settings-tabs">
      <TabsList aria-label="Settings sections"><TabsTrigger value="general">General</TabsTrigger><TabsTrigger value="api-key">API key</TabsTrigger></TabsList>
      <TabsContent value="general" className="settings-panel">
        <Facts rows={[
          signedIn && ['Name', account.user.name],
          signedIn && ['Email', <span key="email" className="settings-readonly">{account.user.email}<span className="secondary"> · read-only</span></span>],
          ['Project', project.name],
          !signedIn && ['Project ID', <code key="id">{project.id}</code>],
          retention && ['Retention', `Traces are kept for ${retention}, then removed.`],
        ]}/>
      </TabsContent>
      <TabsContent value="api-key" className="settings-panel">
        {signedIn ? <ApiKeyTab account={account}/> : <>
          <div className="settings-card-heading">
            <p id="keys-unavailable" className="settings-note">Local mode does not use API keys. The backend accepts traces only from this computer (loopback) and only while it runs with <code>AGENT_DEBUGGER_LOCAL_MODE=1</code>.</p>
            <button type="button" className="button small" disabled aria-describedby="keys-unavailable">Create API key</button>
          </div>
          <CopyBlock label=".env for your agent" text={`# Where the SDK sends traces. TraceSession.local() uses this address by default.\nAGENT_DEBUGGER_ENDPOINT=${LOCAL_ENDPOINT}\n# Set it to an empty value to turn export off.`}/>
          <p className="settings-note">Next: the <a href={homeHref(project.id)}>Dashboard</a> runs an example agent and confirms its trace arrives.</p>
        </>}
      </TabsContent>
    </Tabs>
  </section>
}
