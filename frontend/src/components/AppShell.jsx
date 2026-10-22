import { useEffect, useRef } from 'react'
import Icon from './Icon.jsx'
import { accountHref, runsHref, settingsHref } from '../app/routes.jsx'
import { returnQuery } from '../features/trace/traceState.js'
import { usePreference, useTheme } from '../app/preferences.js'

export default function AppShell({ projects, project, route, children, header }) {
  const [sidebar, setSidebar] = usePreference('sidebar', ['expanded', 'collapsed'], 'expanded')
  const theme = useTheme()
  const live = project?.dataSource === 'local'
  const main = useRef(null)
  const previousPath = useRef(null)
  useEffect(() => {
    document.title = `${route.settings ? 'Settings' : route.projectsPage ? 'Projects' : route.runId || 'Runs'} · ${project?.name || 'Agent Debugger'} · Agent Debugger`
    if (previousPath.current !== route.path) main.current?.focus()
    previousPath.current = route.path
  }, [route.path, route.runId, route.projectsPage, route.settings, project?.name])
  useEffect(() => {
    function dismiss(event) {
      const open = document.querySelector('details[open]:not([data-inline])')
      if (!open) return
      if (event.type === 'keydown' && event.key === 'Escape') { open.open = false; open.querySelector('summary')?.focus(); event.stopPropagation() }
      if (event.type === 'pointerdown' && !open.contains(event.target)) open.open = false
    }
    document.addEventListener('keydown', dismiss); document.addEventListener('pointerdown', dismiss)
    return () => { document.removeEventListener('keydown', dismiss); document.removeEventListener('pointerdown', dismiss) }
  }, [])
  return <div className="app-shell" data-sidebar={sidebar}>
    <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); main.current?.focus() }}>Skip to content</a>
    <aside className="sidebar" aria-label="Project navigation">
      <div className="brand"><span className="brand-mark"><Icon name="branch"/></span><strong className="nav-text">Agent Debugger</strong></div>
      <div className="project-picker" title={project?.name || 'Choose a project'}>
        <span className="project-avatar" aria-hidden="true">{project?.initial || '?'}</span>
        <div className="project-context"><label className="sr-only" htmlFor="project">Project</label><select id="project" value={project?.id || ''} disabled={!projects.length} onChange={event => { window.location.hash = runsHref(event.target.value).slice(1) }}>
          {!project && <option value="" disabled>{projects.length ? 'Choose a project' : 'No projects available'}</option>}
          {projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select><span className="nav-text">{project?.environment || 'Project access'}</span></div>
      </div>
      <nav aria-label="Project workspaces"><a className={`nav-item ${project && !route.settings ? 'active' : ''}`} href={projects.length ? runsHref(project?.id || projects[0].id, returnQuery(route.search)) : undefined} aria-disabled={!projects.length || undefined} aria-label="Runs" aria-current={project && !route.runId && !route.settings ? 'page' : undefined} title="Runs"><Icon name="runs"/><span className="nav-text">Runs</span></a>
        {!live && <a className={`nav-item ${route.projectsPage ? 'active' : ''}`} href="#/projects" aria-label="Projects" aria-current={route.projectsPage ? 'page' : undefined} title="Projects"><Icon name="branch"/><span className="nav-text">Projects</span></a>}
      </nav>
      <div className="sidebar-bottom">{!live && project && <a className={`nav-item ${route.settings ? 'active' : ''}`} href={settingsHref(project.id)} title="Project settings" aria-label="Project settings" aria-current={route.settings ? 'page' : undefined}><Icon name="settings"/><span className="nav-text">Settings</span></a>}
        {!live && <a className="nav-item" href={accountHref('login', route.path + (route.search ? '?' + route.search : ''))} title="Sign in — authentication not connected" aria-label="Sign in — authentication not connected"><Icon name="arrow"/><span className="nav-text">Sign in</span></a>}
        <div className="appearance-control" title={`Appearance: ${theme.preference}`}><Icon name="theme"/><label className="sr-only" htmlFor="appearance">Appearance</label><select id="appearance" value={theme.preference} onChange={event => theme.setPreference(event.target.value)}><option value="light">Light appearance</option><option value="dark">Dark appearance</option><option value="system">System appearance</option></select></div>
        <div className="sidebar-divider"/><button className="nav-item sidebar-toggle" aria-label={`${sidebar === 'expanded' ? 'Collapse' : 'Expand'} sidebar`} aria-expanded={sidebar === 'expanded'} title={`${sidebar === 'expanded' ? 'Collapse' : 'Expand'} sidebar`} onClick={() => setSidebar(sidebar === 'expanded' ? 'collapsed' : 'expanded')}><Icon name="panel"/><span className="nav-text">Collapse sidebar</span></button>
      </div>
    </aside>
    <div className="workspace">{header || <header className="app-header"><nav aria-label="Breadcrumb" className="breadcrumbs">{route.projectsPage || route.settings ? <><a href="#/projects" aria-current={route.projectsPage === 'list' ? 'page' : undefined}>Projects</a>{(route.settings || route.projectsPage === 'new') && <><span aria-hidden="true">/</span><span aria-current="page">{route.settings ? 'Settings' : 'Create'}</span></>}</> : <><a href={projects.length ? runsHref(project?.id || projects[0].id, returnQuery(route.search)) : '#/projects'} aria-current={!route.runId ? 'page' : undefined}>Runs</a>{route.runId && <><span aria-hidden="true">/</span><span aria-current="page">{route.runId}</span></>}</>}</nav>{live && <span className="sample-badge" title="Actual SDK spans received over HTTP; temporary backend memory. Not production persistence.">Captured SDK data</span>}</header>}
      <main className="page" id="main-content" tabIndex="-1" ref={main}>{children}</main>
    </div>
  </div>
}
