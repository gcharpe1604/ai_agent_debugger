import { useEffect, useState } from 'react'

// A tagged, cancelled read: no stale result can cross attempt/source boundaries.
function useRead(repository, method, args) {
  const serialized = JSON.stringify(args)
  const [response, setResponse] = useState(null), [revision, setRevision] = useState(0)
  const key = `${method}:${serialized}:${revision}`
  useEffect(() => {
    const controller = new AbortController(); let current = true
    Promise.resolve().then(() => repository[method]({ ...JSON.parse(serialized), signal: controller.signal })).then(
      data => { if (current) setResponse({ key, data }) },
      error => { if (current && error?.name !== 'AbortError') setResponse({ key, error: error?.message || 'Evidence read failed' }) },
    )
    return () => { current = false; controller.abort() }
  }, [repository, method, serialized, key])
  return { data: response?.key === key ? response.data : null, busy: response?.key !== key, error: response?.key === key ? response.error : null, retry: () => setRevision(n => n + 1) }
}
export function useInvestigationRead(repository, projectId, runId) { return useRead(repository, 'readInvestigation', { projectId, runId }) }
export function useEvidenceRead(repository, projectId, runId, attemptId, citationId) { return useRead(repository, 'readSource', { projectId, runId, attemptId, citationId }) }
