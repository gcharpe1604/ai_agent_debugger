import { useEffect, useRef, useState } from 'react'
import { runsHref } from '../../app/routes.jsx'
import Icon from '../../components/Icon.jsx'

// These commands are the local development and controlled example commands in docs/local-development.md.
const backendCommand = "$env:AGENT_DEBUGGER_LOCAL_MODE = '1'\nuv run --project backend --locked uvicorn agent_debugger_api.main:app --host 127.0.0.1 --port 8008 --workers 1 --no-proxy-headers"
const exampleCommand = 'uv run --directory examples/tool_task_agent --locked python -m tool_task_agent run TOOL-01'

function Command({ value, label }) {
  const [notice, setNotice] = useState('')

  async function copy() {
    try {
      await navigator.clipboard.writeText(value)
      setNotice('Command copied.')
    } catch {
      setNotice('Clipboard unavailable. Select and copy the command.')
    }
  }

  return <div className="setup-command">
    <pre><code>{value}</code></pre>
    <button type="button" className="button small" onClick={copy} aria-label={`Copy ${label} command`}><Icon name="copy"/>Copy</button>
    <span className="secondary setup-copy-notice" role="status">{notice}</span>
  </div>
}

// Three checks that take a new user from nothing to an opened trace:
// the backend answers, an example agent runs, and its trace ID can be read back.
export default function SetupGuide({ traceRepository, projectId, connected, checking, checkConnection }) {
  const [traceId, setTraceId] = useState('')
  const [verification, setVerification] = useState(null)
  const request = useRef(null)
  useEffect(() => () => request.current?.abort(), [])

  function resetVerification() {
    request.current?.abort()
    request.current = null
    setVerification(null)
  }

  async function verify(event) {
    event.preventDefault()
    if (!connected || checking || request.current) return
    const id = traceId.trim().toLowerCase()
    if (!/^[0-9a-f]{32}$/.test(id)) {
      setVerification({ error: 'Enter the 32-character trace ID printed by the example.', invalidId: true })
      return
    }

    const controller = new AbortController()
    request.current = controller
    setVerification({ pending: true })
    try {
      const trace = await traceRepository.readTrace({ projectId, runId: id, signal: controller.signal })
      if (trace.run.traceId !== id || !trace.spans.length) throw new Error('No captured spans were found for this trace ID.')
      if (!controller.signal.aborted) setVerification({ id, received: trace.spans.length })
    } catch (error) {
      if (!controller.signal.aborted) setVerification({ error: error?.message || 'Could not read the trace. Try again.' })
    } finally {
      if (request.current === controller) request.current = null
    }
  }

  return <section className="home-section sdk-setup" aria-labelledby="setup-heading">
    <header className="home-section-heading">
      <h2 id="setup-heading">Send your first trace</h2>
      <p className="secondary">Three checks: the backend answers, an example agent runs, and its trace arrives here.</p>
    </header>
    <ol className="setup-steps">
      <li>
        <h3>Check the backend</h3>
        <p className="secondary">Local captures are held in temporary memory. Restarting the backend clears them.</p>
        <div className="setup-actions">
          <button type="button" className="button small" disabled={checking} onClick={() => { resetVerification(); checkConnection() }}><Icon name="refresh"/>Check connection</button>
          <span className="badge" data-state={checking ? undefined : connected ? 'ok' : 'error'} role="status">{checking ? 'Checking backend…' : connected ? 'Backend reachable' : 'Backend unavailable'}</span>
        </div>
        {!connected && !checking && <div className="setup-instructions">
          <p>From the repository root in PowerShell, start the backend, then check the connection again.</p>
          <Command value={backendCommand} label="backend start"/>
        </div>}
      </li>
      <li>
        <h3>Run a controlled example</h3>
        <p className="secondary">Run this from the repository root. This example uses local tools and needs no model API key.</p>
        <Command value={exampleCommand} label="controlled example"/>
      </li>
      <li>
        <h3>Verify the captured trace</h3>
        <p id="setup-trace-help" className="secondary">Paste the ID from the export receipt in your terminal.</p>
        <form className="setup-verify" onSubmit={verify}>
          <label htmlFor="setup-trace-id">Trace ID</label>
          <div className="setup-verify-fields">
            <input id="setup-trace-id" className="mono" value={traceId} onChange={event => { resetVerification(); setTraceId(event.target.value) }} maxLength={64} spellCheck={false} autoComplete="off" aria-invalid={verification?.invalidId || undefined} aria-describedby={verification?.error ? 'setup-trace-help setup-trace-error' : 'setup-trace-help'}/>
            <button className="button solid" disabled={!connected || checking || verification?.pending} type="submit">{verification?.pending ? 'Verifying…' : 'Verify trace'}</button>
          </div>
        </form>
        {verification?.error && <p id="setup-trace-error" className="error-text" role="alert">{verification.error}</p>}
        {verification?.id && <div className="setup-actions">
          <span className="badge" data-state="ok" role="status">{verification.received} {verification.received === 1 ? 'span' : 'spans'} received</span>
          <a className="button" href={runsHref(projectId, '', verification.id)}>Open trace<Icon name="arrow"/></a>
        </div>}
      </li>
    </ol>
  </section>
}
