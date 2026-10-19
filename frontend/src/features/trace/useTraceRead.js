import { useEffect, useState } from 'react'

// Tagged results ensure that an older selection can never render under a new ID.
export function useTraceRead(repository, projectId, runId, limit) {
  const [response, setResponse] = useState(null)
  const [retry, setRetry] = useState(0)
  const scope = `${projectId}/${runId}`, key = `${scope}/${limit ?? 'initial'}/${retry}`
  useEffect(() => {
    const controller = new AbortController()
    let current = true
    repository.readTrace({ projectId, runId, limit, signal: controller.signal }).then(
      data => { if (current) setResponse({ key, scope, data }) },
      error => { if (current && error?.name !== 'AbortError') setResponse(previous => ({ key, scope, data: previous?.scope === scope ? previous.data : null, error: error?.message || 'Trace read failed' })) },
    )
    return () => { current = false; controller.abort() }
  }, [repository, projectId, runId, limit, scope, key])
  return { data: response?.scope === scope ? response.data : null, busy: response?.key !== key, error: response?.key === key ? response.error : null, retry: () => setRetry(n => n + 1) }
}
export function useSpanRead(repository, projectId, runId, spanId) {
  const [response, setResponse] = useState(null)
  const [retry, setRetry] = useState(0)
  const key = `${projectId}/${runId}/${spanId}/${retry}`
  useEffect(() => {
    if (!spanId) return
    const controller = new AbortController()
    let current = true
    repository.readSpan({ projectId, runId, spanId, signal: controller.signal }).then(
      data => { if (current) setResponse({ key, data }) },
      error => { if (current && error?.name !== 'AbortError') setResponse({ key, error: error?.message || 'Span read failed' }) },
    )
    return () => { current = false; controller.abort() }
  }, [repository, projectId, runId, spanId, key])
  return { data: response?.key === key ? response.data : null, busy: !!spanId && response?.key !== key, error: response?.key === key ? response.error : null, retry: () => setRetry(n => n + 1) }
}
