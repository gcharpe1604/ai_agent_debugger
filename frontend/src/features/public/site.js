// Facts shared by the landing page and the docs.
export const REPO_URL = 'https://github.com/gcharpe1604/ai_agent_debugger'
export const SDK_INSTALL = 'pip install "git+https://github.com/gcharpe1604/ai_agent_debugger.git#subdirectory=sdk/python"'

// The ingest endpoint of the site the reader is on (Vercel, a VM or localhost),
// so copied snippets point at a real server.
export function ingestEndpoint() {
  const origin = typeof window !== 'undefined' && /^https?:/.test(window.location.origin) ? window.location.origin : 'https://<your-host>'
  return `${origin}/api/v1/traces`
}

export const envSnippet = () => `AGENT_DEBUGGER_ENDPOINT=${ingestEndpoint()}
AGENT_DEBUGGER_API_KEY=adbg_sk_...`

export const minimalAgent = `from dotenv import load_dotenv
from ai_agent_debugger_sdk import TraceSession

load_dotenv()  # AGENT_DEBUGGER_ENDPOINT and AGENT_DEBUGGER_API_KEY

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
