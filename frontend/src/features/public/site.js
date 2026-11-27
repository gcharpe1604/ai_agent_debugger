import { docsUrl } from '../../app/routes.jsx'

// Facts and links used by the landing page.
export const REPO_URL = 'https://github.com/gcharpe1604/ai_agent_debugger'
export const SDK_INSTALL = 'pip install "git+https://github.com/gcharpe1604/ai_agent_debugger.git#subdirectory=sdk/python"'

// Docs-site pages linked from the landing page. Every path must be in
// DOCS_PAGES (docsPages.js); `npm run build` checks it.
export const DOCS = {
  home: docsUrl(),
  quickstart: docsUrl('get-started/quickstart/'),
  traceSession: docsUrl('sdk/trace-session/'),
  retries: docsUrl('concepts/errors-and-retries/'),
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

export const traceSessionSnippet = `from ai_agent_debugger_sdk import TraceSession

# TraceSession reads AGENT_DEBUGGER_ENDPOINT and AGENT_DEBUGGER_API_KEY
# from the environment; with no endpoint it records nothing.

class Tools:
    def search(self, query):
        return {"hits": 3}

with TraceSession("my-agent") as tracing:
    tools = tracing.instrument(
        Tools(),
        {"search": ("tool", "Tools.search")},
        payloads={"search": (lambda query: {"query": query}, lambda result: result)},
    )
    with tracing.operation("agent", "MyAgent.run"):
        tools.search("refund policy")`
