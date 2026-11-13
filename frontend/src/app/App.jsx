import { useState } from 'react'
import AppShell from '../components/AppShell.jsx'
import RunExplorerPage from '../pages/RunExplorerPage.jsx'
import RunDetailPage from '../pages/RunDetailPage.jsx'
import { disconnectedRuns, disconnectedTraces, disconnectedInvestigations, disconnectedProjects } from '../data/disconnectedAdapters.js'
import EvidencePage from '../features/evidence/EvidencePage.jsx'
import ReadBoundary from '../components/ReadBoundary.jsx'
import { returnQuery } from '../features/trace/traceState.js'
import { runsHref, useRoute } from './routes.jsx'
import { disconnectedAccount } from '../data/accessAdapters.js'
import useProjects from '../features/access/useProjects.js'
import ProjectsPage from '../features/access/ProjectsPage.jsx'
import AccountPage from '../features/access/AccountPage.jsx'
import AccessState from '../features/access/AccessState.jsx'
import HomePage from '../pages/HomePage.jsx'
import SettingsPage from '../pages/SettingsPage.jsx'

function ProjectWorkspace({ repository, traceRepository, investigationRepository, route, project, projects }) {
  const [traceViews] = useState(() => new Map())
  const [evidenceViews] = useState(() => new Map())
  const protect = children => <ReadBoundary key={route.path} back={runsHref(project.id, returnQuery(route.search))}>{children}</ReadBoundary>
  // A new project key remounts this scope; no old span/finding selection crosses projects.
  if (route.evidence) return protect(<EvidencePage key={`${project.id}/${route.runId}`} repository={investigationRepository} route={route} project={project} projects={projects} cache={evidenceViews}/> )
  if (route.runId) return protect(<RunDetailPage key={`${project.id}/${route.runId}`} repository={traceRepository} investigationRepository={investigationRepository} route={route} project={project} projects={projects} cache={traceViews}/> )
  return protect(<RunExplorerPage key={project.id} project={project} projects={projects} route={route} repository={repository} traceRepository={traceRepository}/>)
}

export default function App({ repository = disconnectedRuns, traceRepository = disconnectedTraces, investigationRepository = disconnectedInvestigations, projectAdapter = disconnectedProjects, accountAdapter = disconnectedAccount }) {
  const route = useRoute()
  const adapter = projectAdapter
  const state = useProjects(adapter)
  const projects = state.projects
  const project = projects.find(item => item.id === route.projectId)
  const local = adapter.mode === 'local'
  const fallbackProjectId = project?.id || projects[0]?.id || (local ? 'local' : null)
  const protect = children => <ReadBoundary key={route.path} back={fallbackProjectId ? runsHref(fallbackProjectId, returnQuery(route.search)) : '#/projects'}>{children}</ReadBoundary>
  // Local Home stays usable while the backend is offline: its setup steps are
  // how the user gets it running.
  if (route.home && local && route.projectId === 'local') return protect(<HomePage project={project} projects={projects} route={route} local repository={repository} traceRepository={traceRepository} checking={state.busy} checkConnection={state.retry}/>)
  if (route.home && project) return protect(<HomePage key={project.id} project={project} projects={projects} route={route} local={false} repository={repository}/>)
  if (route.home && local) return protect(<AppShell projects={projects} project={project} route={route} local><AccessState kind="unavailable"/></AppShell>)
  if (project?.dataSource === 'local' && route.settings) return protect(<AppShell projects={projects} project={project} route={route}><SettingsPage project={project}/></AppShell>)
  if (project?.dataSource === 'local' && route.evidence) return protect(<AppShell projects={projects} project={project} route={route}><AccessState kind="unavailable"/></AppShell>)
  // Account/access routes unmount project workspaces, dropping rendered trace/evidence caches.
  // Disconnected authentication never fabricates or blocks captured local telemetry.
  if (route.account) return protect(<AccountPage key={route.path} route={route} adapter={accountAdapter}/> )
  if (project && !route.settings && !state.error) return <ProjectWorkspace key={project.id} repository={repository} traceRepository={traceRepository} investigationRepository={investigationRepository} route={route} project={project} projects={projects}/>
  return protect(<AppShell projects={projects} project={project} route={route} local={local}>
    {route.projectsPage || route.settings ? <ProjectsPage route={route} project={project} state={state} adapter={adapter}/>
      : state.error ? <AccessState kind={state.error} retry={state.retry} target={route.path}/>
        : !projects.length && (!state.busy || adapter.initialProjects) ? <ProjectsPage route={route} project={project} state={state} adapter={adapter}/>
          : state.busy ? <p role="status">Loading projects…</p>
            : <AccessState kind="unavailable"/>}
  </AppShell>)
}
