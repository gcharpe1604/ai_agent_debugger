import { useState, useEffect } from 'react'

export function useRuns(repository, projectId, query, queryKey) {
  const [refresh, setRefresh] = useState(0)
  const [response, setResponse] = useState(null)
  const scope = `${projectId}?${queryKey}`
  const key = `${scope}:${refresh}`
  useEffect(() => {
    const controller = new AbortController()
    let current = true
    repository.listRuns({ projectId, query, signal: controller.signal }).then(
      result => { if (current) setResponse({ key, scope, result, error: null }) },
      error => { if (current && error.name !== 'AbortError') setResponse(previous => ({ key, scope, result: previous?.scope === scope ? previous.result : null, error: error.message || 'Unable to read runs' })) },
    )
    return () => { current = false; controller.abort() }
  }, [repository, projectId, query, scope, key])
  return { result: response?.scope === scope ? response.result : null, error: response?.key === key ? response.error : null, busy: response?.key !== key, refresh: () => setRefresh(value => value + 1) }
}
