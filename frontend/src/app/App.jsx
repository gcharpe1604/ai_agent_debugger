import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import AppShell from '../components/AppShell.jsx'
import RunExplorerPage from '../pages/RunExplorerPage.jsx'
import RunDetailPage from '../pages/RunDetailPage.jsx'
import { disconnectedRuns, disconnectedTraces, disconnectedInvestigations, disconnectedProjects } from '../data/disconnectedAdapters.js'
import EvidencePage from '../features/evidence/EvidencePage.jsx'
import ReadBoundary from '../components/ReadBoundary.jsx'
import { returnQuery } from '../features/trace/traceState.js'
import { accountHref, homeHref, isPublic, replaceHash, runsHref, settingsHref, useRoute } from './routes.jsx'
import { disconnectedAccount } from '../data/accessAdapters.js'
import useProjects from '../features/access/useProjects.js'
import ProjectsPage from '../features/access/ProjectsPage.jsx'
import AccountPage from '../features/access/AccountPage.jsx'
import AccessState from '../features/access/AccessState.jsx'
import HomePage from '../pages/HomePage.jsx'
import SettingsPage from '../pages/SettingsPage.jsx'
import { AccountContext } from '../features/access/session.js'
import { DURABLE_PROJECT } from '../data/durableRepository.js'

// Landing and docs: a separate chunk, so the app bundle does not grow.
const PublicSite = lazy(() => import('../features/public/PublicSite.jsx'))
function Public({ route, dashboard, signedIn }) {
  return <Suspense fallback={<p className="session-check" role="status">Loading…</p>}><PublicSite route={route} dashboard={dashboard} signedIn={signedIn}/></Suspense>
}

// Replaces the current history entry, so Back does not loop through the redirect.
function Redirect({ href }) {
  useEffect(() => { replaceHash(href) }, [href])
  return null
}

function ProjectWorkspace({ repository, traceRepository, investigationRepository, route, project, projects }) {
  const [traceViews] = useState(() => new Map())
  const [evidenceViews] = useState(() => new Map())
  const protect = children => <ReadBoundary key={route.path} back={runsHref(project.id, returnQuery(route.search))}>{children}</ReadBoundary>
  // A new project key remounts this scope; no old span/finding selection crosses projects.
  if (route.evidence) return protect(<EvidencePage key={`${project.id}/${route.runId}`} repository={investigationRepository} route={route} project={project} projects={projects} cache={evidenceViews}/> )
  if (route.runId) return protect(<RunDetailPage key={`${project.id}/${route.runId}`} repository={traceRepository} investigationRepository={investigationRepository} route={route} project={project} projects={projects} cache={traceViews}/> )
  return protect(<RunExplorerPage key={project.id} project={project} projects={projects} route={route} repository={repository} traceRepository={traceRepository}/>)
}

function Workspace({ repository = disconnectedRuns, traceRepository = disconnectedTraces, investigationRepository = disconnectedInvestigations, projectAdapter = disconnectedProjects, accountAdapter = disconnectedAccount }) {
  const route = useRoute()
  const adapter = projectAdapter
  const state = useProjects(adapter)
  const projects = state.projects
  const project = projects.find(item => item.id === route.projectId)
  const local = adapter.mode === 'local'
  // The durable source has one project per account: no project list or switcher.
  const durable = adapter.mode === 'durable'
  const fallbackProjectId = project?.id || projects[0]?.id || (local ? 'local' : durable ? DURABLE_PROJECT : null)
  const protect = children => <ReadBoundary key={route.path} back={fallbackProjectId ? runsHref(fallbackProjectId, returnQuery(route.search)) : '#/projects'}>{children}</ReadBoundary>
  if (isPublic(route)) return <Public route={route} dashboard={fallbackProjectId ? homeHref(fallbackProjectId) : '#/projects'} signedIn={local || durable}/>
  // No Profile page: the account is shown in Settings › General.
  if (route.profile) return <Redirect href={fallbackProjectId ? settingsHref(fallbackProjectId) : '#/projects'}/>
  if (durable && !route.account && (route.projectsPage || !route.projectId)) return <Redirect href={homeHref(DURABLE_PROJECT)}/>
  // Local Home stays usable while the backend is offline: its setup steps are
  // how the user gets it running.
  if (route.home && local && route.projectId === 'local') return protect(<HomePage project={project} projects={projects} route={route} local repository={repository} traceRepository={traceRepository} checking={state.busy} checkConnection={state.retry}/>)
  if (route.home && project) return protect(<HomePage key={project.id} project={project} projects={projects} route={route} local={false} repository={repository}/>)
  if (route.home && local) return protect(<AppShell projects={projects} project={project} route={route} local><AccessState kind="unavailable"/></AppShell>)
  if (project?.dataSource === 'local' && route.settings) return protect(<AppShell projects={projects} project={project} route={route}><SettingsPage project={project} initialTab={new URLSearchParams(route.search).get('tab')}/></AppShell>)
  if (project?.dataSource === 'local' && route.evidence) return protect(<AppShell projects={projects} project={project} route={route}><AccessState kind="unavailable"/></AppShell>)
  // Account/access routes unmount project workspaces, dropping rendered trace/evidence caches.
  // Disconnected authentication never fabricates or blocks captured local telemetry.
  if (route.account) return protect(<AccountPage key={route.path} route={route} adapter={accountAdapter}/> )
  if (project && !route.settings && !state.error) return <ProjectWorkspace key={project.id} repository={repository} traceRepository={traceRepository} investigationRepository={investigationRepository} route={route} project={project} projects={projects}/>
  if (durable) return protect(<AppShell projects={projects} project={project} route={route}>
    {state.error ? <AccessState kind={state.error} retry={state.retry} target={route.path}/> : state.busy ? <p role="status">Loading projects…</p> : <AccessState kind="unavailable"/>}
  </AppShell>)
  return protect(<AppShell projects={projects} project={project} route={route} local={local}>
    {route.projectsPage || route.settings ? <ProjectsPage route={route} project={project} state={state} adapter={adapter}/>
      : state.error ? <AccessState kind={state.error} retry={state.retry} target={route.path}/>
        : !projects.length && (!state.busy || adapter.initialProjects) ? <ProjectsPage route={route} project={project} state={state} adapter={adapter}/>
          : state.busy ? <p role="status">Loading projects…</p>
            : <AccessState kind="unavailable"/>}
  </AppShell>)
}

// Durable source: every read needs a session. Nothing project-scoped renders or
// reads until GET /auth/me names a user; account pages render at any time.
function DurableApp(props) {
  const { accountAdapter } = props
  const route = useRoute()
  const [session, setSession] = useState({ state: 'checking' })
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const controller = new AbortController(); let current = true
    accountAdapter.readSession({ signal: controller.signal }).then(
      result => { if (current) setSession(result.state === 'signed-in' ? result : { state: 'signed-out' }) },
      error => { if (current && error?.name !== 'AbortError') setSession({ state: 'error' }) },
    )
    return () => { current = false; controller.abort() }
  }, [accountAdapter, revision])
  // A 401 on a data read lands on session-expired: the session is gone.
  // (State adjusted during render when the route changes, not in an effect.)
  const [seenAccountRoute, setSeenAccountRoute] = useState(route.account)
  if (route.account !== seenAccountRoute) {
    setSeenAccountRoute(route.account)
    if (route.account === 'session-expired') setSession({ state: 'signed-out' })
  }
  const target = route.path + (route.search ? '?' + route.search : '')
  const publicPage = isPublic(route)
  useEffect(() => { if (session.state === 'signed-out' && !route.account && !publicPage) replaceHash(accountHref('login', target)) }, [session.state, route.account, publicPage, target])
  const setUser = useCallback(user => setSession({ state: 'signed-in', user }), [])
  const signOut = useCallback(async () => {
    // An already-ended session is signed out too; other failures reach the button.
    try { await accountAdapter.signOut() } catch (error) { if (error?.kind !== 'expired') throw error }
    setSession({ state: 'signed-out' })
    replaceHash(accountHref('login', `/projects/${DURABLE_PROJECT}`))
  }, [accountAdapter])
  const user = session.state === 'signed-in' ? session.user : null
  const account = useMemo(() => ({ user, adapter: accountAdapter, setUser, signOut }), [user, accountAdapter, setUser, signOut])
  let content
  // Public pages never wait for the session check (a sleeping API can take a minute).
  if (publicPage) content = <Public route={route} dashboard={homeHref(DURABLE_PROJECT)} signedIn={!!user}/>
  else if (route.account) content = <AccountPage key={route.path} route={route} adapter={accountAdapter} onSignedIn={setUser}/>
  else if (user) content = <Workspace key={user.id} {...props}/>
  else if (session.state === 'error') content = <div className="account-shell"><main className="account-main"><AccessState kind="session" retry={() => { setSession({ state: 'checking' }); setRevision(value => value + 1) }}/></main></div>
  else content = <p className="session-check" role="status">{session.state === 'checking' ? 'Checking your session…' : 'Redirecting to sign in…'}</p>
  return <AccountContext.Provider value={account}>{content}</AccountContext.Provider>
}

export default function App(props) {
  // The adapter set is fixed for the page's lifetime, so the branch never flips.
  return props.accountAdapter?.mode === 'durable' ? <DurableApp {...props}/> : <Workspace {...props}/>
}
