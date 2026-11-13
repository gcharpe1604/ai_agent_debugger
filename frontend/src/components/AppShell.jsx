import { useEffect, useRef } from 'react'
import Icon from './Icon.jsx'
import { accountHref, homeHref, runsHref, settingsHref } from '../app/routes.jsx'
import { returnQuery } from '../features/trace/traceState.js'
import { usePreference, useTheme } from '../app/preferences.js'
import { hasModifier, isTyping } from '../app/keyboard.js'

const DOCS_URL = 'https://github.com/gcharpe1604/ai_agent_debugger/tree/main/docs'

// Local mode serves exactly one in-memory project, so its switcher is a menu
// that names it rather than a choice. Other modes use a real project select.
function ProjectSwitcher({ projects, project, local, projectName }) {
  if (local) return <details className="project-menu">
    <summary title={`${projectName} · temporary storage`}>
      <span className="project-avatar" aria-hidden="true">{project?.initial || 'L'}</span>
      <span className="project-name">{projectName}</span>
      <span className="env-tag">Local</span>
      <Icon name="chevron-down"/>
    </summary>
    <div className="menu-popover">
      <p className="menu-label">Project</p>
      <span className="menu-item" aria-current="true">{projectName}<Icon name="check"/></span>
      <p className="menu-note">Local mode has one project, held in backend memory. Projects arrive with durable ingestion.</p>
    </div>
  </details>
  return <div className="project-select">
    <span className="project-avatar" aria-hidden="true">{project?.initial || '?'}</span>
    <label className="sr-only" htmlFor="project">Project</label>
    <select id="project" value={project?.id || ''} disabled={!projects.length} onChange={event => { window.location.hash = runsHref(event.target.value).slice(1) }}>
      {!project && <option value="" disabled>{projects.length ? 'Choose a project' : 'No projects available'}</option>}
      {projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select>
    {project?.environment && <span className="env-tag">{project.environment}</span>}
  </div>
}

// crumbs: the page trail after the project, e.g. [<a>Tracing</a>, 'abc…'].
// actions: the page's own controls (Refresh, Download JSON).
// header: an extra page header rendered under the top bar (evidence pages).
export default function AppShell({ projects, project, route, children, header, crumbs, actions, local = project?.dataSource === 'local' }) {
  const [sidebar, setSidebar] = usePreference('sidebar', ['expanded', 'collapsed'], 'expanded')
  const theme = useTheme()
  const projectName = project?.name || (local ? 'Local captures' : null)
  const projectId = project?.id || projects[0]?.id || (local ? 'local' : null)
  const runsLink = projectId ? runsHref(projectId, returnQuery(route.search)) : undefined
  const tracingActive = !!projectId && route.projectId === projectId && !route.settings && !route.home
  const settingsProjectId = project?.id || (local ? 'local' : null)
  const pageName = route.home ? 'Home' : route.settings ? 'Settings' : route.projectsPage ? 'Projects' : route.runId || 'Tracing'
  const trail = crumbs ?? [pageName]
  const main = useRef(null)
  const previousPath = useRef(null)
  useEffect(() => {
    document.title = `${pageName}${projectName ? ` · ${projectName}` : ''} · Agent Debugger`
    if (previousPath.current !== route.path) main.current?.focus()
    previousPath.current = route.path
  }, [route.path, pageName, projectName])
  useEffect(() => {
    function dismiss(event) {
      const open = document.querySelector('details[open]:not([data-inline])')
      if (!open) return
      // preventDefault marks the Escape as used, so a preview panel behind the menu stays open.
      if (event.type === 'keydown' && event.key === 'Escape') { open.open = false; open.querySelector('summary')?.focus(); event.preventDefault(); event.stopPropagation() }
      if (event.type === 'pointerdown' && !open.contains(event.target)) open.open = false
    }
    document.addEventListener('keydown', dismiss); document.addEventListener('pointerdown', dismiss)
    return () => { document.removeEventListener('keydown', dismiss); document.removeEventListener('pointerdown', dismiss) }
  }, [])
  useEffect(() => {
    // "/" jumps to the page's search box, unless the user is already typing.
    function shortcut(event) {
      if (event.key !== '/' || hasModifier(event) || isTyping(event.target)) return
      const search = main.current?.querySelector('[data-shortcut="search"]')
      if (search) { event.preventDefault(); search.focus(); search.select?.() }
    }
    document.addEventListener('keydown', shortcut)
    return () => document.removeEventListener('keydown', shortcut)
  }, [])
  const navItem = (label, href, icon, active, extra = {}) => <a className={`nav-item ${active ? 'active' : ''}`} href={href} aria-disabled={!href || undefined} aria-label={extra.ariaLabel || label} aria-current={active ? extra.current || 'page' : undefined} title={extra.title || label} {...extra.link}><Icon name={icon}/><span className="nav-text">{label}</span>{extra.after}</a>
  return <div className="app-shell" data-sidebar={sidebar}>
    <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); main.current?.focus() }}>Skip to content</a>
    <aside className="sidebar" aria-label="Project navigation">
      <div className="brand">
        <span className="brand-mark" title="Agent Debugger"><Icon name="branch"/></span>
        <strong className="nav-text">Agent Debugger</strong>
      </div>
      <nav aria-label="Project workspaces">
        {navItem('Home', projectId ? homeHref(projectId) : undefined, 'home', !!route.home)}
        <span className="section-label nav-text" aria-hidden="true">Observability</span>
        {navItem('Tracing', runsLink, 'runs', tracingActive, { current: route.runId ? 'location' : 'page' })}
        {!local && navItem('Projects', '#/projects', 'branch', !!route.projectsPage)}
      </nav>
      <div className="sidebar-bottom">
        {settingsProjectId && navItem('Settings', settingsHref(settingsProjectId), 'settings', !!route.settings, { ariaLabel: 'Project settings', title: 'Project settings' })}
        {navItem('Docs', DOCS_URL, 'docs', false, { ariaLabel: 'Docs (opens in a new tab)', title: 'Documentation (opens in a new tab)', link: { target: '_blank', rel: 'noreferrer' }, after: <span className="nav-text nav-external" aria-hidden="true"><Icon name="external"/></span> })}
        {!local && navItem('Sign in', accountHref('login', route.path + (route.search ? '?' + route.search : '')), 'arrow', false, { ariaLabel: 'Sign in — authentication not connected', title: 'Sign in — authentication not connected' })}
        <div className="sidebar-divider"/>
        {local && <div className="profile-row" title="Local mode has no accounts or sign-in"><span className="profile-avatar" aria-hidden="true"><Icon name="user"/></span><span className="nav-text profile-text"><strong>Local developer</strong><span>Local mode · no sign-in</span></span></div>}
        <div className="appearance-control" title={`Appearance: ${theme.preference}`}><Icon name="theme"/><label className="sr-only" htmlFor="appearance">Appearance</label><select id="appearance" value={theme.preference} onChange={event => theme.setPreference(event.target.value)}><option value="light">Light appearance</option><option value="dark">Dark appearance</option><option value="system">System appearance</option></select></div>
      </div>
    </aside>
    <div className="workspace">
      <header className="topbar">
        <button className="sidebar-toggle" aria-label={sidebar === 'expanded' ? 'Collapse sidebar' : 'Expand sidebar'} aria-expanded={sidebar === 'expanded'} title={sidebar === 'expanded' ? 'Collapse sidebar' : 'Expand sidebar'} onClick={() => setSidebar(sidebar === 'expanded' ? 'collapsed' : 'expanded')}><Icon name="panel-left"/></button>
        <ProjectSwitcher projects={projects} project={project} local={local} projectName={projectName}/>
        {!header && trail.length > 0 && <nav aria-label="Breadcrumb" className="breadcrumbs">
          {trail.map((crumb, index) => <span key={index} className="crumb" aria-current={index === trail.length - 1 && typeof crumb === 'string' ? 'page' : undefined}><span className="crumb-separator" aria-hidden="true">/</span>{crumb}</span>)}
        </nav>}
        {actions && <div className="topbar-actions">{actions}</div>}
      </header>
      {header}
      <main className="page" id="main-content" tabIndex="-1" ref={main}>{children}</main>
    </div>
  </div>
}
