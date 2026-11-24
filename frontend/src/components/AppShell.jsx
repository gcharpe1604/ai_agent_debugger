import { useEffect, useRef, useState } from 'react'
import Icon from './Icon.jsx'
import Select from './ui/Select.jsx'
import Tooltip, { TooltipProvider } from './ui/Tooltip.jsx'
import { Menu, MenuContent, MenuItem, MenuLabel, MenuRadioGroup, MenuRadioItem, MenuSeparator, MenuTrigger } from './ui/Menu.jsx'
import { accountHref, homeHref, runsHref, settingsHref } from '../app/routes.jsx'
import { returnQuery } from '../features/trace/traceState.js'
import { usePreference, useTheme } from '../app/preferences.js'
import { hasModifier, isTyping } from '../app/keyboard.js'
import { useAccount } from '../features/access/session.js'

const DOCS_URL = 'https://github.com/gcharpe1604/ai_agent_debugger/tree/main/docs'
const themes = [['light', 'Light'], ['dark', 'Dark'], ['system', 'System']]

// Fixture/preview mode only: several projects to choose from. The local and
// durable sources each have exactly one project, named in the breadcrumb.
function ProjectSelect({ projects, project }) {
  const options = projects.map(item => ({ value: item.id, label: item.name }))
  return <Select className="project-select" aria-label="Project" value={project?.id || ''} disabled={!projects.length} placeholder={projects.length ? 'Choose a project' : 'No projects available'} options={options} onValueChange={id => { window.location.hash = runsHref(id).slice(1) }}/>
}

// Sidebar footer: who is signed in, theme and Sign out, in one menu.
function UserMenu({ account, local, collapsed }) {
  const theme = useTheme()
  const [state, setState] = useState('idle')
  const user = account?.user
  const name = user ? user.name : local ? 'Local developer' : 'Not signed in'
  const detail = user ? user.email : local ? 'No sign-in' : null
  async function signOut() {
    setState('busy')
    try { await account.signOut() } catch { setState('failed') }
  }
  return <>
    <Menu>
      <Tooltip content={name} side="right" disabled={!collapsed}>
        <MenuTrigger>
          <button type="button" className="user-button" aria-label={`Account menu: ${name}`}>
            <span className="user-avatar" aria-hidden="true">{(user?.name || name).trim().charAt(0).toUpperCase()}</span>
            <span className="nav-text user-text"><strong>{name}</strong>{detail && <span>{detail}</span>}</span>
            <span className="nav-text user-chevron" aria-hidden="true"><Icon name="chevrons-up-down"/></span>
          </button>
        </MenuTrigger>
      </Tooltip>
      <MenuContent className="user-menu" side="top" align="start">
        <MenuLabel className="user-menu-identity"><strong>{name}</strong>{detail && <span>{detail}</span>}</MenuLabel>
        <MenuSeparator/>
        <MenuLabel>Appearance</MenuLabel>
        {/* One segmented control: Light | Dark | System. Arrow keys still move between them. */}
        <MenuRadioGroup aria-label="Appearance" value={theme.preference} onValueChange={theme.setPreference} className="segmented theme-segmented">
          {themes.map(([value, label]) => <MenuRadioItem key={value} value={value} indicator={false} className="theme-segment" onSelect={event => event.preventDefault()}>{label}</MenuRadioItem>)}
        </MenuRadioGroup>
        {user && <><MenuSeparator/><MenuItem disabled={state === 'busy'} onSelect={signOut}><Icon name="sign-out"/>{state === 'busy' ? 'Signing out…' : 'Sign out'}</MenuItem></>}
      </MenuContent>
    </Menu>
    {state === 'failed' && <p className="user-menu-error" role="alert">Sign-out failed. Retry.</p>}
  </>
}

// crumbs: the page trail after the project, e.g. [<a>Tracing</a>, 'abc…'].
// actions: the page's own controls (Refresh, Download JSON).
// header: an extra page header rendered under the top bar (evidence pages).
export default function AppShell(props) {
  return <TooltipProvider><Shell {...props}/></TooltipProvider>
}

function Shell({ projects, project, route, children, header, crumbs, actions, local = project?.dataSource === 'local' }) {
  const account = useAccount()
  const [sidebar, setSidebar] = usePreference('sidebar', ['expanded', 'collapsed'], 'expanded')
  const collapsed = sidebar === 'collapsed'
  // The durable source (signed-in account) and the local profile each serve one project.
  const durable = !!account || project?.storage === 'durable'
  const singleProject = durable || local
  const projectName = project?.name || (local ? 'Local captures' : null)
  const projectId = project?.id || projects[0]?.id || (local ? 'local' : null)
  const runsLink = projectId ? runsHref(projectId, returnQuery(route.search)) : undefined
  const tracingActive = !!projectId && route.projectId === projectId && !route.settings && !route.home
  const settingsProjectId = project?.id || (local ? 'local' : null)
  const pageName = route.home ? 'Dashboard' : route.settings ? 'Settings' : route.projectsPage ? 'Projects' : route.runId || 'Tracing'
  const trail = crumbs ?? [pageName]
  const main = useRef(null)
  const previousPath = useRef(null)
  useEffect(() => {
    document.title = `${pageName}${projectName ? ` · ${projectName}` : ''} · Agent Debugger`
    if (previousPath.current !== route.path) main.current?.focus()
    previousPath.current = route.path
  }, [route.path, pageName, projectName])
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
  const navItem = (label, href, icon, active, extra = {}) => <Tooltip key={label} content={extra.tooltip || label} side="right" disabled={!collapsed}>
    <a className={`nav-item${active ? ' active' : ''}`} href={href} aria-disabled={!href || undefined} aria-label={extra.ariaLabel || label} aria-current={active ? extra.current || 'page' : undefined} {...extra.link}><Icon name={icon}/><span className="nav-text">{label}</span>{extra.after}</a>
  </Tooltip>
  const projectCrumb = singleProject && projectName && (projectId ? <a href={homeHref(projectId)}>{projectName}</a> : projectName)
  return <div className="app-shell" data-sidebar={sidebar}>
    <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); main.current?.focus() }}>Skip to content</a>
    <aside className="sidebar" aria-label="Project navigation">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true"><Icon name="branch"/></span>
        <strong className="nav-text">Agent Debugger</strong>
      </div>
      <nav className="sidebar-nav" aria-label="Project workspaces">
        {navItem('Dashboard', projectId ? homeHref(projectId) : undefined, 'dashboard', !!route.home)}
        {navItem('Tracing', runsLink, 'runs', tracingActive, { current: route.runId ? 'location' : 'page' })}
        {!singleProject && navItem('Projects', '#/projects', 'branch', !!route.projectsPage)}
        {settingsProjectId && navItem('Settings', settingsHref(settingsProjectId), 'settings', !!route.settings, { ariaLabel: 'Project settings', tooltip: 'Project settings' })}
      </nav>
      <div className="sidebar-bottom">
        {navItem('Docs', DOCS_URL, 'docs', false, { ariaLabel: 'Docs (opens in a new tab)', tooltip: 'Docs', link: { target: '_blank', rel: 'noreferrer' }, after: <span className="nav-text nav-external" aria-hidden="true"><Icon name="external"/></span> })}
        {!singleProject && navItem('Sign in', accountHref('login', route.path + (route.search ? '?' + route.search : '')), 'arrow', false, { ariaLabel: 'Sign in — authentication not connected', tooltip: 'Sign in' })}
      </div>
      <div className="sidebar-footer">
        <UserMenu account={account} local={local && !durable} collapsed={collapsed}/>
      </div>
    </aside>
    <div className="workspace">
      <header className="topbar">
        <button type="button" className="button ghost icon-only sidebar-toggle" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} onClick={() => setSidebar(collapsed ? 'expanded' : 'collapsed')}><Icon name="panel-left"/></button>
        {!singleProject && <ProjectSelect projects={projects} project={project}/>}
        {!header && (projectCrumb || trail.length > 0) && <nav aria-label="Breadcrumb" className="breadcrumbs">
          {projectCrumb && <span className="crumb crumb-project">{projectCrumb}</span>}
          {trail.map((crumb, index) => <span key={index} className="crumb" aria-current={index === trail.length - 1 && typeof crumb === 'string' ? 'page' : undefined}>{(projectCrumb || index > 0 || !singleProject) && <span className="crumb-separator" aria-hidden="true">/</span>}{crumb}</span>)}
        </nav>}
        {actions && <div className="topbar-actions">{actions}</div>}
      </header>
      {header}
      <main className="page" id="main-content" tabIndex="-1" ref={main}>{children}</main>
    </div>
  </div>
}
