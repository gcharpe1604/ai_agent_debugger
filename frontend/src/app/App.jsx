import { useMemo, useState } from 'react'
import AppShell from '../components/AppShell.jsx'
import RunExplorerPage from '../pages/RunExplorerPage.jsx'
import RunDetailPage from '../pages/RunDetailPage.jsx'
import { fixtureRepository, selectRuns } from '../data/runRepository.js'
import { traceRepository as fixtureTraceRepository } from '../data/traceRepository.js'
import { investigationRepository as fixtureInvestigationRepository } from '../data/investigationRepository.js'
import EvidencePage from '../features/evidence/EvidencePage.jsx'
import ReadBoundary from '../components/ReadBoundary.jsx'
import { returnQuery } from '../features/trace/traceState.js'
import { runsHref, useRoute } from './routes.jsx'
import { createFixtureProjects, disconnectedAccount } from '../data/accessAdapters.js'
import useProjects from '../features/access/useProjects.js'
import ProjectsPage from '../features/access/ProjectsPage.jsx'
import AccountPage from '../features/access/AccountPage.jsx'
import AccessState from '../features/access/AccessState.jsx'

function ProjectWorkspace({ repository, traceRepository, investigationRepository, route, project, projects }) {
  const [traceViews] = useState(() => new Map())
  const [evidenceViews] = useState(() => new Map())
  const protect = children => <ReadBoundary key={route.path} back={runsHref(project.id, returnQuery(route.search))}>{children}</ReadBoundary>
  // A new project key remounts this scope; no old span/finding selection crosses projects.
  if (route.evidence) return protect(<EvidencePage key={`${project.id}/${route.runId}`} repository={investigationRepository} route={route} project={project} projects={projects} cache={evidenceViews}/> )
  if (route.runId) return protect(<RunDetailPage key={`${project.id}/${route.runId}`} repository={traceRepository} investigationRepository={investigationRepository} route={route} project={project} projects={projects} cache={traceViews}/> )
  return protect(<AppShell projects={projects} project={project} route={route}><RunExplorerPage key={project.id} project={project} search={route.search} repository={repository}/></AppShell>)
}

export default function App({ repository = fixtureRepository, traceRepository = fixtureTraceRepository, investigationRepository = fixtureInvestigationRepository, projectAdapter, accountAdapter = disconnectedAccount }) {
  const route = useRoute()
  const adapter = useMemo(() => projectAdapter || createFixtureProjects(repository.projects), [projectAdapter, repository])
  const state = useProjects(adapter)
  const projects = state.projects
  const project = projects.find(item => item.id === route.projectId)
  const scopedRepository = useMemo(() => ({ ...repository, listRuns: args => {
    if (adapter.mode === 'fixture' && !repository.projects.some(p => p.id === args.projectId)) return Promise.resolve(selectRuns([], args.projectId, args.query))
    return repository.listRuns(args)
  } }), [repository, adapter])
  const protect = children => <ReadBoundary key={route.path} back={runsHref(project?.id || projects[0]?.id || 'agent-examples', returnQuery(route.search))}>{children}</ReadBoundary>
  // Account/access routes unmount project workspaces, dropping rendered trace/evidence caches.
  // Sample routes are deliberately not gated by disconnected authentication.
  if (route.account) return protect(<AccountPage key={route.path} route={route} adapter={accountAdapter}/> )
  if (project && !route.settings && !state.error) return <ProjectWorkspace key={project.id} repository={scopedRepository} traceRepository={traceRepository} investigationRepository={investigationRepository} route={route} project={project} projects={projects}/>
  return protect(<AppShell projects={projects} project={project} route={route}>
    {route.projectsPage || route.settings ? <ProjectsPage route={route} project={project} state={state} adapter={adapter}/>
      : state.error ? <AccessState kind={state.error} retry={state.retry} target={route.path}/>
        : !projects.length && (!state.busy || adapter.initialProjects) ? <ProjectsPage route={route} project={project} state={state} adapter={adapter}/>
          : state.busy ? <p role="status">Loading projects…</p>
            : <AccessState kind="unavailable"/>}
  </AppShell>)
}
