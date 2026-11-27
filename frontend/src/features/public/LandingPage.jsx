import { accountHref } from '../../app/routes.jsx'
import Architecture from './Architecture.jsx'
import { CodeCard, CopyButton, Highlighted } from './Code.jsx'
import { DOCS, SDK_INSTALL, envSnippet, traceSessionSnippet } from './site.js'

// Real screenshots of the Demo account at 2x (docs/frontend/screenshots.md).
// Width and height are the file's pixels; CSS scales them.
const SHOTS = {
  hero: { width: 2400, height: 1034, alt: 'Trace view of a failed live tool-task-agent run: the span tree with model, API and tool spans and their durations, and the failed Order tool call open on the Errors tab with its recorded ToolError.' },
  failed: { width: 1568, height: 1002, alt: 'Tracing filtered to Status: Failed: failed runs from the langgraph-workflow, research-planning and tool-task agents, with latency, span count and error count.' },
  tree: { width: 1390, height: 654, alt: 'Trace tree of a live tool-task-agent run: the run, the agent, two model calls with their chat/completions requests and the failed Order tool call, each with a duration bar.' },
  inspector: { width: 1008, height: 1084, alt: 'Span inspector for the failed "Order · attempt 1" tool call: status ERROR, the captured error payload with type ToolError and its message, and the recorded exception event.' },
  dashboard: { width: 1520, height: 1494, alt: 'Dashboard tiles for traces, error rate and p50 and p95 latency, a Latency by agent table for four agents, and Recent failures with each run\'s first error.' },
}

function Shot({ name, theme, priority = false }) {
  const { width, height, alt } = SHOTS[name]
  return <img className="lp-shot" data-shot={name} src={`/landing/${name}-${theme}.webp`} alt={alt} width={width} height={height} loading={priority ? 'eager' : 'lazy'} decoding="async" fetchPriority={priority ? 'high' : undefined}/>
}

function Ctas({ signedIn, dashboard }) {
  return <div className="lp-ctas">
    {signedIn
      ? <a className="lp-btn lp-btn-primary" href={dashboard}>Open dashboard</a>
      : <a className="lp-btn lp-btn-primary" href={accountHref('register')}>Sign up</a>}
    <a className="lp-btn lp-btn-secondary" href={DOCS.quickstart}>Read the quickstart</a>
  </div>
}

// A section with the label column (≥768 px) and a body.
function Row({ id, label, children, className = '' }) {
  return <section className={`lp-section ${className}`} aria-labelledby={id}>
    <div className="lp-container lp-row">
      <p className="lp-label lp-row-label">{label}</p>
      <div className="lp-row-body">{children}</div>
    </div>
  </section>
}

const STEPS = [
  ['Create an account', 'Copy your API key when it appears. It is shown once.'],
  ['Install and configure', 'Install the SDK, then export AGENT_DEBUGGER_ENDPOINT and AGENT_DEBUGGER_API_KEY.'],
  ['Wrap your agent', 'Open a TraceSession and name the methods to trace. Nothing is patched globally.'],
]

const SPAN_TYPES = ['agent', 'model', 'tool', 'retrieval']

const FEATURES = [
  {
    key: 'runs', label: '02 · Runs', title: 'Find failed runs across agents',
    text: 'Filter every run by status, search by agent name or trace ID.',
    facts: [['cols', 'Timestamp, name, status, latency, spans, errors'], ['filter', 'Status, time range']],
    shot: 'failed',
  },
  {
    key: 'trace', label: '03 · Trace', title: 'See the whole run',
    text: 'The span tree and the waterfall timeline show every step and how long it took.',
    chips: true,
    facts: [[<span key="retry" className="lp-retry" aria-hidden="true">↻</span>, 'A step that fails, then succeeds on retry, is a recovered retry, not a failed run.']],
    shot: 'tree',
  },
  {
    key: 'inspector', label: '04 · Inspector', title: 'Read the failing step',
    text: 'Every span opens in the inspector: Input / Output, Metadata, Events, Errors.',
    facts: [['redacted', 'Secret field names, recursively'], ['bounded', 'Payload bytes, depth and node count']],
    shot: 'inspector',
  },
  {
    key: 'dashboard', label: '05 · Dashboard', title: 'Watch error rate and latency',
    text: 'Error rate, p50 and p95 latency per agent, and the most recent failures with their first error.',
    facts: [['per agent', 'Runs, p50, p95, error rate']],
    shot: 'dashboard',
  },
]

const pad = number => String(number).padStart(2, '0')

export default function LandingPage({ signedIn, dashboard, theme }) {
  const tabs = [
    { id: 'terminal', label: 'terminal', language: 'shell', text: SDK_INSTALL },
    { id: 'env', label: '.env', language: 'env', text: envSnippet() },
    { id: 'agent', label: 'agent.py', language: 'python', text: traceSessionSnippet },
  ]
  return <>
    <section className="lp-section lp-hero" aria-labelledby="hero-title">
      <div className="lp-container">
        <h1 id="hero-title">Debug AI agents from the trace, not the logs.</h1>
        <div className="lp-hero-intro">
          <p className="lp-lede">An OpenTelemetry SDK for Python agents and a trace view built for them: span tree, waterfall, span inspector.</p>
          <Ctas signedIn={signedIn} dashboard={dashboard}/>
        </div>
        <figure className="lp-figure">
          <figcaption className="lp-caption">
            <span className="lp-failed">● failed</span>
            <span>tool-task-agent</span>
            <span className="lp-wide">trace 877fc441…e8ce</span>
            <span className="lp-wide">7 spans</span>
            <span className="lp-wide">2 errors</span>
          </figcaption>
          <Shot name="hero" theme={theme} priority/>
        </figure>
      </div>
    </section>

    <Row id="quickstart-title" label="01 · Quickstart">
      <h2 id="quickstart-title" className="lp-h2">Instrument in minutes</h2>
      <div className="lp-quickstart">
        <ol className="lp-steps">
          {STEPS.map(([title, text], index) => <li key={title}>
            <span className="lp-step-number" aria-hidden="true">{pad(index + 1)}</span>
            <div><h3>{title}</h3><p>{text}</p></div>
          </li>)}
        </ol>
        <CodeCard tabs={tabs}/>
      </div>
    </Row>

    {FEATURES.map(({ key, label, title, text, chips, facts, shot }) => <Row key={key} id={`${key}-title`} label={label} className="lp-feature">
      <div className="lp-feature-grid">
        <div className="lp-feature-text">
          <h2 id={`${key}-title`} className="lp-h3">{title}</h2>
          <p>{text}</p>
          {chips && <ul className="lp-chips" aria-label="Span types">
            {SPAN_TYPES.map(type => <li key={type} data-type={type}><span className="lp-swatch" aria-hidden="true"/>{type}</li>)}
          </ul>}
          <dl className="lp-facts">
            {facts.map(([term, value], index) => <div key={index}><dt>{term}</dt><dd>{value}</dd></div>)}
          </dl>
        </div>
        <div className="lp-well" data-well={key}><Shot name={shot} theme={theme}/></div>
      </div>
    </Row>)}

    <Row id="architecture-title" label="06 · Architecture">
      <h2 id="architecture-title" className="lp-h2">The span path</h2>
      <Architecture/>
    </Row>

    <section className="lp-section lp-cta" aria-labelledby="cta-title">
      <div className="lp-container">
        <h2 id="cta-title">Trace your first run.</h2>
        <Ctas signedIn={signedIn} dashboard={dashboard}/>
        <div className="lp-install">
          <span className="lp-prompt" aria-hidden="true">$</span>
          <code><Highlighted text={SDK_INSTALL} language="shell" wrapPaths/></code>
          <CopyButton text={SDK_INSTALL} label="install command"/>
        </div>
      </div>
    </section>
  </>
}
