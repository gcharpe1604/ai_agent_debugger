import { useEffect, useRef } from 'react'
import CopyBlock from '../../components/CopyBlock.jsx'
import Icon from '../../components/Icon.jsx'

// Durable ingest (protocol "1"): FastAPI -> Kafka -> trace-writer -> ClickHouse.
export const DURABLE_ENDPOINT = 'http://127.0.0.1:8008/api/v1/traces'

// A new API key, shown once. It lives only in the caller's component state:
// never in the URL, storage or a later read (the backend keeps only its hash).
export default function ApiKeyReveal({ apiKey, Heading = 'h1', onContinue, continueLabel = 'Continue' }) {
  const heading = useRef(null)
  useEffect(() => { heading.current?.focus() }, [])
  return <section className="key-reveal" aria-labelledby="key-heading">
    <Heading id="key-heading" ref={heading} tabIndex="-1">Your API key</Heading>
    <p className="key-warning" role="note"><Icon name="error"/><span><strong>You won’t see this again.</strong> Copy it now. If you lose it, rotate the key in Settings.</span></p>
    <CopyBlock label="API key" text={apiKey}/>
    <p className="settings-note">Set these in your agent’s <code>.env</code> (or environment) so the SDK sends traces to this account:</p>
    <CopyBlock label="SDK setup" text={`AGENT_DEBUGGER_ENDPOINT=${DURABLE_ENDPOINT}\nAGENT_DEBUGGER_API_KEY=${apiKey}`}/>
    {onContinue && <div className="key-reveal-actions"><button type="button" className="button solid" onClick={onContinue}>{continueLabel}</button></div>}
  </section>
}
