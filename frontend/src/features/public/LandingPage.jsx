import CopyBlock from '../../components/CopyBlock.jsx'
import Icon from '../../components/Icon.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/Tabs.jsx'
import { accountHref } from '../../app/routes.jsx'
import { DOCS, SDK_INSTALL, envSnippet, providerSnippet, traceSessionSnippet } from './site.js'

// Real screenshots of the Demo account, cropped at capture time and stored at 2x
// (docs/frontend/screenshots.md). Width and height are CSS pixels.
const SHOTS = {
  hero: { width: 1200, height: 517, alt: 'Trace view of a failed live tool-task-agent run: the span tree with model, API and tool spans and their durations, and the failed Order tool call open on the Errors tab with its recorded ToolError.' },
  failed: { width: 784, height: 501, alt: 'Tracing filtered to Status: Failed: nine failed runs from the langgraph-workflow, research-planning and tool-task agents, with latency, span count and error count.' },
  tree: { width: 695, height: 327, alt: 'Trace tree of a live tool-task-agent run: the run, the agent, two model calls with their chat/completions requests and the failed Order tool call, each with a duration bar.' },
  inspector: { width: 504, height: 542, alt: 'Span inspector for the failed "Order · attempt 1" tool call: status ERROR, the captured error payload with type ToolError and its message, and the recorded exception event.' },
  dashboard: { width: 749, height: 746, alt: 'Dashboard tiles for 26 traces with a 35% error rate and p50 and p95 latency, a Latency by agent table for four agents, and Recent failures with each run\'s first error.' },
}

function Shot({ name, theme, priority = false }) {
  const { width, height, alt } = SHOTS[name]
  return <img className="shot" data-shot={name} src={`/landing/${name}-${theme}.webp`} alt={alt} width={width} height={height} loading={priority ? 'eager' : 'lazy'} decoding="async" fetchPriority={priority ? 'high' : undefined}/>
}

function Window({ children, label }) {
  return <figure className="shot-window">
    <div className="shot-window-bar" aria-hidden="true"><span className="shot-window-dots"><i/><i/><i/></span><span>{label}</span></div>
    {children}
  </figure>
}

const rows = [
  {
    title: 'Find the runs that failed',
    text: 'Filter Tracing to failed runs across every agent. A step that fails and then succeeds on retry is a recovered retry, not a failed run.',
    link: [DOCS.retries, 'Errors and retries'],
    shot: 'failed', label: 'Tracing',
  },
  {
    title: 'See the whole run',
    text: 'Each run is one trace: model calls, tool calls and requests in the order they ran, with a waterfall of durations.',
    link: [DOCS.runsAndSpans, 'Runs and spans'],
    shot: 'tree', label: 'Trace tree',
  },
  {
    title: 'Read the failing step',
    text: 'Open a span to read its input, output and the error it recorded. Secret fields are redacted before they leave your process.',
    link: [DOCS.traceSession, 'Payload capture'],
    shot: 'inspector', label: 'Span inspector',
  },
  {
    title: 'Watch error rate and latency',
    text: 'The Dashboard shows error rate and p50 / p95 latency per agent, and links each recent failure to its first error.',
    link: [DOCS.dashboard, 'Dashboard'],
    shot: 'dashboard', label: 'Dashboard',
  },
]

const architecture = [
  ['Python SDK', 'Spans from your agent'],
  ['Ingest API', 'Checks the key, answers 202'],
  ['Kafka', 'Buffers spans'],
  ['Trace writer', 'Writes batches to ClickHouse'],
  ['ClickHouse', 'Stores spans for fast reads'],
  ['Web UI', 'Rebuilds the tree'],
]

function PrimaryCta({ signedIn, dashboard }) {
  return signedIn
    ? <a className="button solid large" href={dashboard}>Open dashboard<Icon name="arrow"/></a>
    : <a className="button solid large" href={accountHref('register')}>Sign up<Icon name="arrow"/></a>
}

export default function LandingPage({ signedIn, dashboard, theme }) {
  return <>
    <section className="landing-hero" aria-labelledby="hero-title">
      <h1 id="hero-title">Find the step where your AI agent went wrong.</h1>
      <p className="landing-lede">Trace every model call, tool call and retry, then open the span that failed.</p>
      <div className="landing-ctas">
        <PrimaryCta signedIn={signedIn} dashboard={dashboard}/>
        <a className="button large" href={DOCS.quickstart}>Read the quickstart</a>
      </div>
      <Window label="Trace view"><Shot name="hero" theme={theme} priority/></Window>
    </section>

    <section className="landing-section landing-instrument" aria-labelledby="instrument-title">
      <div className="landing-instrument-text">
        <h2 id="instrument-title" className="landing-title">Instrument in minutes</h2>
        <ol className="landing-steps">
          <li><strong>Create an account</strong><p>Copy your API key. It is shown once; rotate it in Settings.</p></li>
          <li><strong>Install the SDK</strong><CopyBlock label="Terminal" text={SDK_INSTALL}/></li>
          <li><strong>Wrap your agent and run it</strong><p>The run appears in Tracing. <a href={DOCS.quickstart}>Quickstart</a></p></li>
        </ol>
      </div>
      <Tabs defaultValue="session" className="landing-code">
        <TabsList aria-label="Code examples">
          <TabsTrigger value="session">TraceSession</TabsTrigger>
          <TabsTrigger value="provider">Own OTel provider</TabsTrigger>
          <TabsTrigger value="env">.env</TabsTrigger>
        </TabsList>
        <TabsContent value="session"><CopyBlock label="Python" text={traceSessionSnippet}/></TabsContent>
        <TabsContent value="provider"><CopyBlock label="Python" text={providerSnippet()}/></TabsContent>
        <TabsContent value="env"><CopyBlock label=".env" text={envSnippet()}/></TabsContent>
      </Tabs>
    </section>

    {rows.map(({ title, text, link, shot, label }, index) => <section key={title} className="landing-section landing-row" data-flip={index % 2 === 1 || undefined} aria-labelledby={`row-${index}`}>
      <div className="landing-row-text">
        <h2 id={`row-${index}`} className="landing-title">{title}</h2>
        <p>{text}</p>
        <a className="landing-link" href={link[0]}>{link[1]}<Icon name="arrow"/></a>
      </div>
      <div className="landing-row-shot" data-shot={shot}><Window label={label}><Shot name={shot} theme={theme}/></Window></div>
    </section>)}

    <section className="landing-section" aria-labelledby="architecture-title">
      <div className="landing-architecture">
        <h2 id="architecture-title">How a trace gets stored</h2>
        <ol>
          {architecture.map(([name, text]) => <li key={name}><strong>{name}</strong><span>{text}</span></li>)}
        </ol>
        <p>PostgreSQL holds accounts and API keys. <a href={DOCS.selfHosting}>Self-host it on one VM</a></p>
      </div>
    </section>

    <section className="landing-section landing-cta" aria-labelledby="cta-title">
      <h2 id="cta-title" className="landing-title">Trace your next agent run.</h2>
      <p className="landing-lede">One API key and two environment variables. Self-host the stack with Docker Compose.</p>
      <div className="landing-ctas">
        <PrimaryCta signedIn={signedIn} dashboard={dashboard}/>
        <a className="button large" href={DOCS.home}>Browse the docs</a>
      </div>
    </section>
  </>
}
