import CopyBlock from '../../components/CopyBlock.jsx'
import { accountHref, docsHref } from '../../app/routes.jsx'
import { REPO_URL, SDK_INSTALL, envSnippet, ingestEndpoint, minimalAgent } from './site.js'

// Docs pages. Every statement here comes from the repository (SDK source,
// backend routes, docs/trace-protocol.md, docs/deployment.md); keep them in step.

const C = ({ children }) => <code className="inline-code">{children}</code>
const Note = ({ kind = 'info', children }) => <aside className={`docs-note ${kind}`}>{children}</aside>
const Table = ({ head, rows }) => <div className="docs-table-wrap"><table className="docs-table">
  <thead><tr>{head.map(cell => <th key={cell} scope="col">{cell}</th>)}</tr></thead>
  <tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, column) => <td key={column}>{cell}</td>)}</tr>)}</tbody>
</table></div>
const H2 = ({ id, children }) => <h2 id={id}>{children}</h2>
const Link = ({ page, children }) => <a href={docsHref(page)}>{children}</a>

export function Introduction() {
  return <>
    <p className="docs-lede">Agent Debugger records what an AI agent actually did during a run (every model call, tool call, retrieval and retry) and lets you inspect it as a tree and a timeline. When a run goes wrong, you open the failing step and read its input, output and error.</p>
    <H2 id="who">Who it is for</H2>
    <p>Developers building Python agents who need to answer “what happened in this run, and which step broke?” without adding print statements and re-running.</p>
    <H2 id="what">What you can do</H2>
    <ul>
      <li>Send traces from your agent with a small Python SDK built on OpenTelemetry.</li>
      <li>See all runs in <strong>Tracing</strong>, filter by status, agent, execution mode and time.</li>
      <li>Open a run: span tree, waterfall, and an inspector with Input, Output, Metadata, Events and Errors.</li>
      <li>Tell real failures from recovered ones: a tool that fails and then succeeds on retry does not make the run fail.</li>
      <li>Watch totals, error rate, latency by agent and recent failures on the <strong>Dashboard</strong>.</li>
    </ul>
    <H2 id="how">How it works</H2>
    <ol>
      <li>The SDK turns each step of your agent into an OpenTelemetry span. One run is one trace.</li>
      <li>Ended spans are sent in batches to <C>POST /api/v1/traces</C> with your API key.</li>
      <li>The API validates them and publishes them to Kafka, a buffer, then answers <C>202</C>.</li>
      <li>A trace writer moves spans from Kafka into ClickHouse.</li>
      <li>The web UI reads them back and rebuilds the tree. Accounts and keys live in PostgreSQL.</li>
    </ol>
    <H2 id="next">Next</H2>
    <p><Link page="quickstart">Quickstart</Link> gets a first trace on screen in about five minutes.</p>
  </>
}

export function Quickstart() {
  return <>
    <p className="docs-lede">From a new account to your first trace. You need Python 3.10 or newer.</p>
    <H2 id="account">1. Create an account</H2>
    <p><a href={accountHref('register')}>Sign up</a> with your name, email and a password. You are signed in and shown your API key, <C>adbg_sk_…</C>.</p>
    <Note kind="warning">The key is shown <strong>once</strong>. Only a hash of it is stored, so it cannot be shown again. If you lose it, go to <strong>Settings → API key → Rotate</strong>; the old key stops working immediately.</Note>
    <H2 id="install">2. Install the SDK</H2>
    <CopyBlock label="Terminal" text={SDK_INSTALL}/>
    <p>The example below also uses <C>python-dotenv</C> to read a <C>.env</C> file: <C>pip install python-dotenv</C>. Plain environment variables work just as well.</p>
    <H2 id="configure">3. Point it at this server</H2>
    <CopyBlock label=".env" text={envSnippet()}/>
    <p>The endpoint must end in <C>/api/v1/traces</C> and use <C>https</C> (plain <C>http</C> is allowed only for <C>localhost</C>/<C>127.0.0.1</C>). Keep <C>.env</C> out of version control.</p>
    <H2 id="instrument">4. Wrap your agent</H2>
    <CopyBlock label="Python" text={minimalAgent}/>
    <p><C>TraceSession</C> opens one run. <C>instrument</C> wraps the methods you name on that one object; <C>operation</C> marks a block of your own code. <Link page="instrumenting">Instrument your agent</Link> explains each part.</p>
    <H2 id="run">5. Run it and open Tracing</H2>
    <p>When the session ends, the SDK flushes and prints one line to stderr:</p>
    <CopyBlock label="Output" text="Trace 4f2a9c1e...: exported (3 acknowledged spans)"/>
    <p>Open <strong>Tracing</strong> in the app and select the run.</p>
    <H2 id="examples">Try the example agents</H2>
    <p>The repository has four example agents in <C>examples/</C>: <C>tool_task_agent</C>, <C>rag_agent</C>, <C>langgraph_workflow_agent</C> and <C>research_planning_agent</C>. Each loads the nearest <C>.env</C> at start and has controlled scenarios that need no model key, including failures and recovered retries:</p>
    <CopyBlock label="PowerShell" text={`cd examples/tool_task_agent
py -3 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -e .
.\\.venv\\Scripts\\python.exe -m tool_task_agent list
.\\.venv\\Scripts\\python.exe -m tool_task_agent run TOOL-01`}/>
    <H2 id="troubleshooting">If nothing shows up</H2>
    <Table head={['You see', 'Meaning', 'Fix']} rows={[
      ['No “Trace …” line', <>The session did nothing: <C>AGENT_DEBUGGER_ENDPOINT</C> is unset or empty.</>, <>Load your <C>.env</C> before creating <C>TraceSession</C>.</>],
      ['“delivery failed” and a 401 warning', 'The API key is missing, wrong or was rotated.', 'Copy a fresh key from Settings → API key.'],
      ['“delivery failed” after retries', <>The server answered <C>503</C>: its buffer (Kafka) is unavailable. The SDK retried 3 times.</>, 'Check the server; see Self-hosting.'],
      ['“delivery failed” at once', <>A <C>413</C> (batch too large) or <C>422</C> (invalid span). Not retried.</>, <>See <Link page="api">HTTP API</Link>.</>],
      ['Exported, but not in Tracing', 'The trace writer has not stored it yet, or you are signed in to another account.', 'Refresh after a few seconds; check the account.'],
    ]}/>
  </>
}

export function Instrumenting() {
  return <>
    <p className="docs-lede">The SDK package is <C>ai_agent_debugger_sdk</C>. For most agents you need one class, <C>TraceSession</C>, and three of its methods.</p>
    <H2 id="session">TraceSession: one run</H2>
    <CopyBlock label="Python" text={`TraceSession(service_name, *, model=None, provider=None, endpoint=None,
             execution_mode="live", capture=None)`}/>
    <ul>
      <li>Used as <C>with TraceSession("my-agent") as tracing:</C>. Entering it starts the root <C>run</C> span; leaving it ends the run, flushes (up to 10 s) and prints the delivery line.</li>
      <li><C>endpoint</C> defaults to <C>AGENT_DEBUGGER_ENDPOINT</C>; the key comes from <C>AGENT_DEBUGGER_API_KEY</C>. With no endpoint the session does nothing and your code runs unchanged.</li>
      <li><C>model</C> and <C>provider</C> are recorded on the run. <C>execution_mode</C> is <C>"live"</C> or <C>"controlled"</C> (deterministic test runs); Tracing can filter on it.</li>
      <li>It uses its own private OpenTelemetry provider. It never replaces your global provider and never patches classes.</li>
      <li>Telemetry errors never replace your agent’s result or raise into your code.</li>
    </ul>
    <H2 id="instrument">instrument: wrap methods on an object</H2>
    <CopyBlock label="Python" text={`tools = tracing.instrument(
    LocalTools(),                                   # your own instance
    {"invoke": ("tool", "LocalTools.invoke")},      # method -> (span type, span name)
    payloads={"invoke": (input_fn, output_fn)},     # optional, see below
)`}/>
    <p>Only the named methods on that one instance are wrapped. Sync and <C>async</C> methods both work. Each call becomes one span of the given type: <C>run</C>, <C>agent</C>, <C>model</C>, <C>retrieval</C>, <C>tool</C>, <C>api</C>, <C>state</C> or <C>custom</C>.</p>
    <H2 id="payloads">Recording inputs and outputs</H2>
    <p>By default a wrapped call records no arguments or results. To record them, give a pair of functions:</p>
    <ul>
      <li><C>input_fn(*args, **kwargs)</C> receives the call’s arguments and returns plain data to store.</li>
      <li><C>output_fn(result)</C> receives the return value.</li>
    </ul>
    <p>Return only built-in types: dict, list, tuple, str, int, float, bool, None. Anything else becomes <C>"[unsupported]"</C>, so convert model objects yourself (for example <C>result.model_dump()</C>). An extractor that raises is ignored. A call that raises records its input and error type, and no output.</p>
    <H2 id="operation">operation: mark your own code</H2>
    <CopyBlock label="Python" text={`with tracing.operation("agent", "Planner.run", {"debugger.step": "plan"}):
    plan = planner.run(request)`}/>
    <p>If an exception escapes the block, the span is marked <C>ERROR</C> with an exception event holding only the exception type, and the exception is re-raised unchanged. A failure you catch inside the block leaves the parent successful.</p>
    <H2 id="retries">Retries</H2>
    <p>Call tool methods with the keyword arguments <C>step_id=</C> (a string) and <C>attempt=</C> (an int). The span is then named <C>LocalTools.invoke · charge · attempt 2</C>, and attempt 2 is linked to attempt 1. If attempt 1 failed and attempt 2 succeeded, the UI shows a recovered retry and the run stays <strong>Completed</strong>.</p>
    <H2 id="result">Marking the run failed</H2>
    <p>Call <C>tracing.record_result(result)</C> at the end. If <C>result.status == "failed"</C> or <C>result.execution_error</C> is set, the run is marked <C>ERROR</C>. An exception escaping the session also fails the run.</p>
    <H2 id="capture">Capture limits and redaction</H2>
    <p>Pass <C>capture=CaptureConfig(...)</C> to change what is recorded:</p>
    <Table head={['Option', 'Default', 'Allowed']} rows={[
      [<C>capture_inputs</C>, <C>True</C>, 'bool'],
      [<C>capture_outputs</C>, <C>True</C>, 'bool'],
      [<C>capture_errors</C>, <C>True</C>, 'bool; False also drops exception messages'],
      [<C>max_payload_bytes</C>, '16,384', '64 – 131,072'],
      [<C>max_depth</C>, '8', '0 – 32'],
      [<C>max_nodes</C>, '512', '1 – 10,000'],
      [<C>secret_fields</C>, <C>()</C>, 'extra field names to redact'],
    ]}/>
    <p>Fields named like passwords, API keys, tokens, cookies, authorization headers, client secrets, private keys and credentials are replaced with <C>"[redacted]"</C> at any depth, before the value is measured. Matching ignores case and punctuation.</p>
    <Note kind="warning">Redaction is by field name, not content. A secret inside free text or under an unusual key is not caught; add it to <C>secret_fields</C> or turn capture off for that call.</Note>
    <H2 id="delivery">Delivery</H2>
    <p>Spans are exported in batches by a background processor. A <C>503</C> is retried 3 times (after 1, 2 and 4 s); <C>401</C>, <C>413</C>, <C>422</C>, other errors and connection failures drop the batch at once. Stack traces are never exported; the error payload is <C>{'{"type", "message"}'}</C>.</p>
    <H2 id="otel">Using your own OpenTelemetry provider</H2>
    <p>If your app already configures OpenTelemetry, use the lower-level <C>Debugger</C> and <C>DurableSpanExporter</C>:</p>
    <CopyBlock label="Python" text={`from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from ai_agent_debugger_sdk import CaptureConfig, Debugger, DurableSpanExporter

capture = CaptureConfig(secret_fields=("session_id",))
provider = TracerProvider(resource=Resource.create({"service.name": "my-agent"}))
provider.add_span_processor(BatchSpanProcessor(
    DurableSpanExporter("${ingestEndpoint()}", capture, api_key="adbg_sk_...")
))
debugger = Debugger("my-agent", capture=capture, tracer_provider=provider)

with debugger.run("support-run"):
    with debugger.tool("lookup") as span:
        span.set_input({"query": "sample"})
        span.set_output({"found": True})`}/>
    <p><C>Debugger</C> offers <C>run</C>, <C>agent</C>, <C>model</C>, <C>tool</C> and <C>retrieval</C> context managers; each yields a handle with <C>set_input</C>, <C>set_output</C> and <C>set_attribute</C>. Use <C>BatchSpanProcessor</C>, not <C>SimpleSpanProcessor</C>. Full reference: <C>sdk/python/README.md</C>.</p>
  </>
}

export function Concepts() {
  return <>
    <H2 id="run">Run and trace</H2>
    <p>A <strong>run</strong> is one execution of your agent. It is one OpenTelemetry trace, identified by a 32-character hex <C>trace_id</C>. Its outcome comes from the root <C>run</C> span: <strong>Completed</strong> (OK), <strong>Failed</strong> (ERROR) or <strong>Unknown</strong> (no status or no root recorded).</p>
    <H2 id="span">Span</H2>
    <p>A <strong>span</strong> is one step with a start and an end: a model call, a tool call, a block of agent code. It has a 16-character <C>span_id</C>, an optional parent, a type, a status (<C>UNSET</C>, <C>OK</C> or <C>ERROR</C>), attributes, events and up to three payloads.</p>
    <Table head={['Type', 'Use it for']} rows={[
      [<C>run</C>, 'The root of a run (TraceSession creates it)'],
      [<C>agent</C>, 'An agent or workflow step that contains other steps'],
      [<C>model</C>, 'A call to a language model'],
      [<C>retrieval</C>, 'Fetching documents or context'],
      [<C>tool</C>, 'A tool or function the agent invokes'],
      [<C>api</C>, 'An outbound HTTP or database call (status ≥ 400 marks it ERROR)'],
      [<C>state</C>, 'Reading or writing memory or state'],
      [<C>custom</C>, 'Anything else, such as deterministic test doubles'],
    ]}/>
    <p>Parent–child means “ran inside”, not “caused”. Spans can arrive in any order; a child that arrives before its parent is kept, and the run is shown as partial rather than dropped.</p>
    <H2 id="errors">Errors and recovered retries</H2>
    <p>A span is <C>ERROR</C> when an exception escaped it. A child can fail while its parent succeeds, because your code caught the failure. When a failed tool attempt is followed by a successful attempt of the same step, it is a <strong>recovered retry</strong>: the error is still visible on the span, but the run is not a failure.</p>
    <H2 id="payloads">Payloads</H2>
    <p>Each span can carry an <strong>input</strong>, an <strong>output</strong> and an <strong>error</strong> payload, each with a state:</p>
    <Table head={['State', 'Meaning']} rows={[
      [<C>captured</C>, 'Stored as recorded'],
      [<C>redacted</C>, 'At least one secret field was replaced by "[redacted]"'],
      [<C>truncated</C>, 'Cut to fit a limit; still valid JSON'],
      [<C>disabled</C>, 'Capture was turned off; no payload'],
      [<C>unavailable</C>, 'Not recorded, failed, or not JSON; no payload'],
    ]}/>
    <p>The SDK cuts payloads to 16 KiB by default (up to 128 KiB). The server never truncates: a payload over 131,072 bytes is rejected with <C>422</C>.</p>
    <H2 id="projects">Accounts and projects</H2>
    <p>Each account has one project. The server takes the project from your API key, never from the request body, so a key can only write to its own project and the UI only shows your own runs.</p>
  </>
}

export function UsingTheUi() {
  return <>
    <H2 id="dashboard">Dashboard</H2>
    <p>Totals for a time range (last 24 hours, 7 days, 30 days or all time): <strong>Traces</strong>, <strong>Error rate</strong>, <strong>p50</strong> and <strong>p95 latency</strong>. Below them: traces over time, latency by agent, and the most recent failed runs.</p>
    <H2 id="tracing">Tracing</H2>
    <p>One row per run: name, start time, outcome, duration, span count, errors. Use it to find the run you want.</p>
    <ul>
      <li><strong>Search</strong> by agent name or trace ID. Press <kbd>/</kbd> to jump to the search box.</li>
      <li><strong>Filters</strong>: status (Completed, Failed, Unknown), execution mode (live, controlled), agent, and time range.</li>
      <li><strong>Peek</strong>: click a row (or its eye button) to preview the run beside the table without leaving the list.</li>
    </ul>
    <H2 id="trace">Trace view</H2>
    <ul>
      <li><strong>Header</strong>: outcome, duration, span count and error count.</li>
      <li><strong>Tree</strong>: spans nested as they ran, with guide lines and a small waterfall bar on each row showing when it ran within the run.</li>
      <li><strong>Inspector</strong>: select a span to see <strong>Input</strong>, <strong>Output</strong>, <strong>Metadata</strong>, <strong>Events</strong> and <strong>Errors</strong>. JSON is shown in a collapsible viewer, with the payload state (redacted, truncated…) labelled.</li>
      <li><strong>Download JSON</strong> saves the run.</li>
      <li>Keyboard: <kbd>Esc</kbd> closes the inspector; <kbd>F6</kbd> moves focus between tree and inspector.</li>
    </ul>
    <H2 id="debugging">A typical debugging pass</H2>
    <ol>
      <li>Dashboard → <strong>Recent failures</strong>, or Tracing filtered to <strong>Failed</strong>.</li>
      <li>Open the run and look for the red span in the tree.</li>
      <li>Read its <strong>Errors</strong> tab, then its <strong>Input</strong>: was the call wrong, or did the dependency fail?</li>
      <li>Walk up to the parent to see what the agent decided before that call.</li>
    </ol>
    <H2 id="settings">Settings</H2>
    <p><strong>General</strong> shows your account. <strong>API key</strong> shows the key prefix and lets you rotate the key; the new key is shown once and the old one stops working. Light, dark or system theme is in the account menu at the bottom of the sidebar.</p>
  </>
}

export function Api() {
  return <>
    <p className="docs-lede">All endpoints are under <C>/api/v1</C>. Errors are JSON: <C>{'{"detail": ...}'}</C>. Validation errors list field locations and messages, never the submitted values.</p>
    <H2 id="ingest">Ingest traces</H2>
    <CopyBlock label="HTTP" text={`POST /api/v1/traces
Authorization: Bearer adbg_sk_...
Content-Type: application/json

{"protocol_version": "1", "spans": [ ... ]}`}/>
    <p>The SDK builds this request for you. Body limit 4 MiB. Unknown fields are rejected. The key is checked before the body is read.</p>
    <Table head={['Status', 'Meaning', 'Retry?']} rows={[
      [<C>202</C>, <>Every span is in the buffer (Kafka). Not yet stored in ClickHouse. Body: <C>{'{"status": "accepted", "spans": n}'}</C></>, '—'],
      [<C>401</C>, 'Missing, invalid or rotated API key', 'No'],
      [<C>413</C>, 'Body over 4 MiB, or one span too large as a Kafka record. Nothing was published.', 'No'],
      [<C>415</C>, <>Content type is not <C>application/json</C></>, 'No'],
      [<C>422</C>, 'Invalid batch, e.g. a bad ID or a payload over 131,072 bytes. Nothing was published.', 'No'],
      [<C>503</C>, <>Buffer unavailable; nothing accepted. Has <C>Retry-After</C>.</>, 'Yes, the whole batch'],
    ]}/>
    <H2 id="span-fields">Span fields</H2>
    <Table head={['Field', 'Type']} rows={[
      [<C>trace_id</C>, '32 lowercase hex characters (required)'],
      [<C>span_id</C>, '16 lowercase hex characters (required)'],
      [<C>parent_span_id</C>, '16 hex characters or null'],
      [<C>name</C>, 'non-empty string (required)'],
      [<C>operation_type</C>, 'run, agent, model, retrieval, tool, api, state or custom (required)'],
      [<><C>start_time</C>, <C>end_time</C></>, 'integer nanoseconds since the Unix epoch (required)'],
      [<C>status</C>, <C>{'{"code": "UNSET" | "OK" | "ERROR", "description": ""}'}</C>],
      [<><C>attempt</C>, <C>retry_of_span_id</C></>, 'retry metadata'],
      [<><C>model</C>, <C>provider</C>, <C>input_tokens</C>, <C>output_tokens</C>, <C>total_tokens</C>, <C>cost</C></>, <>model metadata; <C>cost</C> is a decimal string</>],
      [<><C>input_payload</C>, <C>output_payload</C>, <C>error_payload</C></>, 'strings up to 131,072 UTF-8 bytes'],
      [<><C>input_state</C>, <C>output_state</C>, <C>error_state</C></>, 'captured, redacted, truncated, disabled or unavailable'],
      [<><C>attributes</C>, <C>events</C>, <C>links</C></>, 'extra data, events and explicit relations'],
    ]}/>
    <p><C>project_id</C> and <C>received_at</C> are set by the server and rejected if sent. Full contract: <C>docs/trace-protocol.md</C>.</p>
    <H2 id="auth">Accounts</H2>
    <p>The browser session is a signed cookie. These endpoints are used by the web app:</p>
    <Table head={['Request', 'Result']} rows={[
      [<C>POST /auth/register</C>, <>Body <C>{'{name, email, password}'}</C>. <C>201</C> with the user and the API key (shown once); starts a session. <C>409</C> if the email exists, <C>403</C> if sign-up is disabled.</>],
      [<C>POST /auth/login</C>, <>Body <C>{'{email, password}'}</C>. <C>204</C>; <C>401</C> for a wrong email or password.</>],
      [<C>POST /auth/logout</C>, <><C>204</C>; ends the session.</>],
      [<C>GET /auth/me</C>, <>The signed-in user: <C>id</C>, <C>name</C>, <C>email</C>, <C>key_prefix</C>.</>],
      [<C>POST /auth/key/rotate</C>, 'A new API key (shown once); the old key stops working.'],
    ]}/>
    <H2 id="read">Reading runs</H2>
    <p>Session cookie required. There is one project per account, named <C>default</C>.</p>
    <Table head={['Request', 'Result']} rows={[
      [<C>GET /projects/default/runs</C>, <>Runs, newest first. Query: <C>started_from</C>, <C>started_to</C> (Unix ns), <C>limit</C> (1–200, default 50), <C>cursor</C> (the previous page’s <C>next_cursor</C>).</>],
      [<C>GET /projects/default/runs/{'{trace_id}'}</C>, 'The run summary, the rebuilt tree and every span (without payload text).'],
      [<C>GET /projects/default/runs/{'{trace_id}'}/spans/{'{span_id}'}</C>, 'One span with its payloads.'],
      [<C>GET /health</C>, <><C>200</C> when the API can reach PostgreSQL, otherwise <C>503</C>.</>],
    ]}/>
  </>
}

export function SelfHosting() {
  return <>
    <p className="docs-lede">The whole stack runs on one VM with Docker Compose: Caddy (HTTPS and the web UI) → API → Kafka → trace writer → ClickHouse, plus PostgreSQL for accounts.</p>
    <H2 id="requirements">Requirements</H2>
    <ul>
      <li>Ubuntu 24.04, 2 vCPU, 4 GB RAM, 30 GB disk.</li>
      <li>Open inbound ports 22, 80 and 443 only. Kafka, ClickHouse, PostgreSQL and the API stay on the internal network.</li>
      <li>A domain pointing at the VM. Without one, <C>{'<ip-with-dashes>'}.sslip.io</C> works.</li>
    </ul>
    <H2 id="deploy">Deploy</H2>
    <CopyBlock label="Shell" text={`git clone ${REPO_URL}.git && cd ai_agent_debugger
sudo bash scripts/deploy/vm-setup.sh     # Docker, compose plugin, swap; safe to re-run
# log out and back in

cp .env.prod.example .env.prod
nano .env.prod                           # SITE_ADDRESS, replace every CHANGE_ME

docker compose -f compose.prod.yaml up -d --build
docker compose -f compose.prod.yaml ps   # all healthy; kafka-init "Exited (0)"`}/>
    <p>Then open <C>{'https://<SITE_ADDRESS>'}</C>, register and copy your key. Set <C>ALLOW_SIGNUP=false</C> in <C>.env.prod</C> once your accounts exist. Database migrations run each time the API starts.</p>
    <H2 id="operate">Operate</H2>
    <CopyBlock label="Shell" text={`git pull && docker compose -f compose.prod.yaml up -d --build    # update
docker compose -f compose.prod.yaml logs -f api trace-writer       # logs
docker compose -f compose.prod.yaml restart trace-writer           # restart one service`}/>
    <Note kind="warning"><C>down</C> keeps your data; <C>down -v</C> deletes every volume: all traces, users and TLS certificates. Back up with a VM snapshot.</Note>
    <p>Single broker and single database node, no replication: losing the disk loses the data. Full guide: <C>docs/deployment.md</C>. For development without Docker, see <C>docs/local-development.md</C>.</p>
  </>
}

export function Limits() {
  return <>
    <H2 id="limits">Current limits</H2>
    <ul>
      <li>Python SDK only. Other languages can post protocol “1” batches to the HTTP API directly.</li>
      <li>Only ended spans are exported: a step that is still running, or lost in a hard crash, is not visible.</li>
      <li>One project per account; no teams or sharing yet.</li>
      <li>Redaction matches field names, not content.</li>
      <li>Single-node deployment, no replication.</li>
      <li>A hosted instance without Kafka and ClickHouse can sign you up and issue keys, but cannot store traces; the Dashboard and Tracing then show “unavailable”. Self-host the full stack to store traces.</li>
    </ul>
    <H2 id="roadmap">Roadmap</H2>
    <ul>
      <li><strong>AI investigator</strong>: reads a failed run and points to suspicious spans, citing only recorded evidence and saying so when the evidence is not enough. Planned outside the OJT duration.</li>
      <li><strong>Projects and teams</strong>: several projects per account and shared access.</li>
      <li>Replay and counterfactual debugging are future ideas, not planned work.</li>
    </ul>
    <p>Source and issues: <a href={REPO_URL} target="_blank" rel="noreferrer">GitHub</a>.</p>
  </>
}
