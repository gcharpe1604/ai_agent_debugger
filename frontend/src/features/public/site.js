import { docsUrl } from '../../app/routes.jsx'

// Facts and links used by the landing page.
export const REPO_URL = 'https://github.com/gcharpe1604/ai_agent_debugger'
export const SDK_INSTALL = 'pip install "git+https://github.com/gcharpe1604/ai_agent_debugger.git#subdirectory=sdk/python"'

// Pages of the docs site (docs-site/src/content/docs). The docs build fails on a
// broken internal link, but nothing checks these from here: keep them in step.
export const DOCS = {
  home: docsUrl(),
  quickstart: docsUrl('get-started/quickstart/'),
  traceSession: docsUrl('sdk/trace-session/'),
  opentelemetry: docsUrl('sdk/opentelemetry/'),
  retries: docsUrl('concepts/errors-and-retries/'),
  runsAndSpans: docsUrl('concepts/runs-and-spans/'),
  dashboard: docsUrl('product/dashboard/'),
  ingestApi: docsUrl('api/ingest/'),
  selfHosting: docsUrl('self-hosting/docker-compose/'),
  limits: docsUrl('limits/'),
}

// The ingest endpoint of the site the reader is on (Vercel, a VM or localhost),
// so copied snippets point at a real server.
export function ingestEndpoint() {
  const origin = typeof window !== 'undefined' && /^https?:/.test(window.location.origin) ? window.location.origin : 'https://<your-host>'
  return `${origin}/api/v1/traces`
}

export const envSnippet = () => `AGENT_DEBUGGER_ENDPOINT=${ingestEndpoint()}
AGENT_DEBUGGER_API_KEY=adbg_sk_...`

export const traceSessionSnippet = `from dotenv import load_dotenv
from ai_agent_debugger_sdk import TraceSession

load_dotenv()  # AGENT_DEBUGGER_ENDPOINT and AGENT_DEBUGGER_API_KEY

class Tools:
    def search(self, query):
        return {"hits": 3}

with TraceSession("my-agent") as tracing:
    tools = tracing.instrument(
        Tools(),
        {"search": ("tool", "Tools.search")},
        payloads={"search": (lambda q: {"query": q}, lambda r: r)},
    )
    with tracing.operation("agent", "MyAgent.run"):
        tools.search("refund policy")`

export const providerSnippet = () => `from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from ai_agent_debugger_sdk import CaptureConfig, Debugger, DurableSpanExporter

capture = CaptureConfig()
provider = TracerProvider()  # your existing provider
exporter = DurableSpanExporter(
    "${ingestEndpoint()}",
    capture,
    api_key="adbg_sk_...",
)
provider.add_span_processor(BatchSpanProcessor(exporter))
debugger = Debugger("my-agent", capture=capture, tracer_provider=provider)

with debugger.run("support-run"):
    with debugger.tool("lookup") as span:
        span.set_input({"query": "refund policy"})
        span.set_output({"found": True})`
