import { useEffect, useState } from 'react'
import { failureKind } from '../../data/accessAdapters.js'

export default function useProjects(adapter) {
  const [revision, setRevision] = useState(0)
  const [response, setResponse] = useState(null)
  useEffect(() => {
    const controller = new AbortController(); let current = true
    Promise.resolve().then(() => adapter.listProjects({ signal: controller.signal })).then(
      projects => {
        if (!Array.isArray(projects) || projects.some(p => !p || typeof p.name !== 'string' || !/^[a-z0-9-]+$/.test(p.id)) || new Set(projects.map(p => p.id)).size !== projects.length) throw new Error('Unexpected project data')
        if (current) setResponse({ adapter, revision, projects })
      },
    ).catch(error => { if (current && error?.name !== 'AbortError') setResponse({ adapter, revision, error: failureKind(error), projects: [] }) })
    return () => { current = false; controller.abort() }
  }, [adapter, revision])
  const matching = response?.adapter === adapter && response.revision === revision
  return {
    projects: matching ? response.projects : (adapter.initialProjects || []),
    busy: !matching, error: matching ? response.error : null,
    retry: () => setRevision(value => value + 1),
    accept: project => setResponse(previous => ({ adapter, revision, projects: [...(previous?.adapter === adapter ? previous.projects : adapter.initialProjects || []).filter(p => p.id !== project.id), project] })),
  }
}
