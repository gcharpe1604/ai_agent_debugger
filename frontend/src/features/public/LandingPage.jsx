import CopyBlock from '../../components/CopyBlock.jsx'
import Icon from '../../components/Icon.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/Tabs.jsx'
import { accountHref } from '../../app/routes.jsx'
import { DOCS, SDK_INSTALL, envSnippet, providerSnippet, traceSessionSnippet } from './site.js'

// Real screenshots of the app at 1440x900, one per theme (docs/frontend/screenshots.md).
// `crop` shows part of a screenshot: x, y, width, height in screenshot pixels.
const SHOT = { width: 1440, height: 900 }
function Shot({ name, theme, alt, crop, priority = false }) {
  const [x, y, w, h] = crop || [0, 0, SHOT.width, SHOT.height]
  const style = crop ? { '--crop-ratio': `${w} / ${h}`, '--crop-width': `${(SHOT.width / w) * 100}%`, '--crop-x': `${(-x / w) * 100}%`, '--crop-y': `${(-y / w) * 100}%` } : undefined
  return <div className={crop ? 'shot shot-crop' : 'shot'} style={style}>
    <img src={`/landing/${name}-${theme}.webp`} alt={alt} width={SHOT.width} height={SHOT.height} loading={priority ? 'eager' : 'lazy'} decoding="async" fetchPriority={priority ? 'high' : undefined}/>
  </div>
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
    text: 'Filter Tracing to failed runs and open one. A step that fails and then succeeds on retry is a recovered retry, not a failed run.',
    link: [DOCS.retries, 'Errors and retries'],
    shot: { name: 'tracing-failed', crop: [240, 48, 1200, 402], alt: 'Tracing filtered to Status: Failed, listing four failed tool-task-agent runs with their latency, span count and error count.' },
  },
  {
    title: 'See the whole run',
    text: 'Each run is one trace: a tree of agent, model and tool spans in the order they ran, with a waterfall of durations.',
    link: [DOCS.runsAndSpans, 'Runs and spans'],
    shot: { name: 'trace', crop: [240, 48, 696, 552], alt: 'Trace tree of a failed tool-task-agent run: plan, order and reserve succeed, then three pay attempts fail, each with its duration bar.' },
  },
  {
    title: 'Read the failing step',
    text: 'Open a span to read its input, output, metadata and error. Secret fields are redacted before they leave your process.',
    link: [DOCS.traceSession, 'Payload capture'],
    shot: { name: 'trace', crop: [936, 148, 504, 360], alt: 'Span inspector for "Pay · attempt 1" with the Errors tab open, showing a ToolTimeout error and its recorded message.' },
  },
]

const architecture = [
  ['Python SDK', 'OpenTelemetry spans from your agent'],
  ['Ingest API', 'Checks the key, answers 202'],
  ['Kafka', 'Buffers spans'],
  ['ClickHouse', 'Stores spans for fast reads'],
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
      <Window label="Trace view">
        <Shot name="trace" theme={theme} priority alt="Trace view of a failed tool-task-agent run: the span tree with three failed pay attempts on the left, and the first attempt's ToolTimeout error open on the right."/>
      </Window>
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

    {rows.map(({ title, text, link, shot }, index) => <section key={title} className="landing-section landing-row" data-flip={index % 2 === 1 || undefined} aria-labelledby={`row-${index}`}>
      <div className="landing-row-text">
        <h2 id={`row-${index}`} className="landing-title">{title}</h2>
        <p>{text}</p>
        <a className="landing-link" href={link[0]}>{link[1]}<Icon name="arrow"/></a>
      </div>
      <Window label={title}><Shot name={shot.name} theme={theme} crop={shot.crop} alt={shot.alt}/></Window>
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
      <Window label="Dashboard">
        <Shot name="dashboard" theme={theme} alt="Dashboard for the last 7 days: 14 traces, 29% error rate, p50 and p95 latency, a traces-over-time chart, latency by agent and recent failures."/>
      </Window>
    </section>
  </>
}
