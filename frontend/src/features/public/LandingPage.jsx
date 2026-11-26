import CopyBlock from '../../components/CopyBlock.jsx'
import Icon from '../../components/Icon.jsx'
import { accountHref, docsHref } from '../../app/routes.jsx'
import TracePreview from './TracePreview.jsx'
import { SDK_INSTALL, envSnippet, minimalAgent } from './site.js'

const features = [
  ['setup', 'Instrument in a few lines', 'A Python SDK built on OpenTelemetry. Wrap the methods you care about (model calls, tools, retrieval) on your own objects. No global monkey patching.'],
  ['runs', 'See the whole run', 'Every run is one trace: a tree of spans with a waterfall beside it, so you see what ran, in which order, for how long, and where it nested.'],
  ['eye', 'Open the exact step', 'Click a span to read its input, output, metadata, events and error. Secret fields are redacted and payloads are size-bounded before they leave your process.'],
  ['retry', 'Real failures, not noise', 'A tool that fails and then succeeds on retry is recorded as a recovered error. The run still counts as completed, so the failure list shows what actually broke.'],
]

const pipeline = [
  ['Your agent + SDK', 'Spans end in your process and are sent in batches with your API key.'],
  ['Ingest API', 'FastAPI checks the key, validates the batch and answers 202 once it is buffered.'],
  ['Kafka', 'Buffers spans so a slow or restarting database never blocks your agent.'],
  ['Trace writer → ClickHouse', 'Writes spans to a column store built for fast time-range scans.'],
  ['Web UI', 'Rebuilds the tree from stored spans. Accounts live in PostgreSQL.'],
]

function Step({ number, title, children }) {
  return <li className="landing-step"><span className="landing-step-number" aria-hidden="true">{number}</span><div><h3>{title}</h3>{children}</div></li>
}

export default function LandingPage({ signedIn, dashboard }) {
  return <>
    <section className="landing-hero" aria-labelledby="hero-title">
      <div className="landing-hero-text">
        <p className="landing-eyebrow">OpenTelemetry · Python SDK · self-hostable</p>
        <h1 id="hero-title">Find the step where your AI agent went wrong.</h1>
        <p className="landing-lede">Agent Debugger records every model call, tool call and retry in an agent run, then shows it as a tree and a timeline. Open the failing step and read its input, output and error, instead of digging through logs.</p>
        <div className="landing-ctas">
          {signedIn
            ? <a className="button solid large" href={dashboard}>Open dashboard<Icon name="arrow"/></a>
            : <a className="button solid large" href={accountHref('register')}>Create an account<Icon name="arrow"/></a>}
          <a className="button large" href={docsHref('quickstart')}>Read the quickstart</a>
        </div>
      </div>
      <TracePreview/>
    </section>

    <section className="landing-section" aria-labelledby="features-title">
      <h2 id="features-title" className="landing-title">What it does</h2>
      <div className="landing-features">
        {features.map(([icon, title, text]) => <article key={title} className="landing-feature">
          <span className="landing-feature-icon"><Icon name={icon}/></span>
          <h3>{title}</h3>
          <p>{text}</p>
        </article>)}
      </div>
    </section>

    <section className="landing-section" aria-labelledby="pipeline-title">
      <h2 id="pipeline-title" className="landing-title">How a trace gets to your screen</h2>
      <p className="landing-subtitle">Five parts, each with one job. <a href={docsHref('concepts')}>Concepts</a> explains runs and spans; <a href={docsHref('self-hosting')}>Self-hosting</a> runs the whole stack on one VM.</p>
      <ol className="landing-pipeline">
        {pipeline.map(([title, text], index) => <li key={title}>
          <strong>{title}</strong>
          <p>{text}</p>
          {index < pipeline.length - 1 && <span className="landing-pipeline-arrow" aria-hidden="true"><Icon name="arrow"/></span>}
        </li>)}
      </ol>
    </section>

    <section className="landing-section" aria-labelledby="quickstart-title">
      <h2 id="quickstart-title" className="landing-title">Send your first trace</h2>
      <ol className="landing-steps">
        <Step number="1" title="Create an account and copy your API key">
          <p>The key (<span className="mono">adbg_sk_…</span>) is shown once. You can rotate it later in Settings → API key.</p>
        </Step>
        <Step number="2" title="Install the SDK and set two variables">
          <CopyBlock label="Terminal" text={SDK_INSTALL}/>
          <CopyBlock label=".env" text={envSnippet()}/>
        </Step>
        <Step number="3" title="Wrap your agent and run it">
          <CopyBlock label="Python" text={minimalAgent}/>
          <p>The run appears in <strong>Tracing</strong>. <a href={docsHref('instrumenting')}>Instrument your agent</a> covers models, retries and payload capture.</p>
        </Step>
      </ol>
    </section>

    <section className="landing-section landing-status" aria-labelledby="status-title">
      <h2 id="status-title" className="landing-title">Where the project stands</h2>
      <div className="landing-status-grid">
        <div>
          <h3><Icon name="check"/>Works today</h3>
          <ul>
            <li>Python SDK with redaction and payload limits</li>
            <li>Authenticated ingest through Kafka into ClickHouse</li>
            <li>Dashboard, trace list with filters, trace tree, waterfall and span inspector</li>
            <li>Accounts with a show-once, rotatable API key</li>
            <li>One-VM deployment with Docker Compose and HTTPS</li>
          </ul>
        </div>
        <div>
          <h3><Icon name="clock"/>Next</h3>
          <ul>
            <li>An evidence-grounded AI investigator that points to suspicious spans (outside the OJT duration)</li>
            <li>Projects and teams</li>
          </ul>
          <p className="muted"><a href={docsHref('limits')}>Limits and roadmap</a></p>
        </div>
      </div>
    </section>

    <section className="landing-cta" aria-label="Get started">
      <h2>Trace your next agent run.</h2>
      <div className="landing-ctas">
        {signedIn
          ? <a className="button solid large" href={dashboard}>Open dashboard<Icon name="arrow"/></a>
          : <a className="button solid large" href={accountHref('register')}>Create an account<Icon name="arrow"/></a>}
        <a className="button large" href={docsHref()}>Browse the docs</a>
      </div>
    </section>
  </>
}
