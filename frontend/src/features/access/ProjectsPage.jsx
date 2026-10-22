import { useEffect, useRef, useState } from 'react'
import { runsHref, settingsHref } from '../../app/routes.jsx'
import { failureKind, projectNameError } from '../../data/accessAdapters.js'
import AccessState from './AccessState.jsx'
import Icon from '../../components/Icon.jsx'
import './access.css'

export function ProjectForm({ project, adapter, onSaved }) {
  const [name, setName] = useState(project?.name || ''), [error, setError] = useState(''), [requestError, setRequestError] = useState(''), [busy, setBusy] = useState(false), [saved, setSaved] = useState(false), [failure, setFailure] = useState(null)
  const input = useRef(null), active = useRef(true), lock = useRef(false), controller = useRef(null)
  useEffect(() => { active.current = true; return () => { active.current = false; controller.current?.abort() } }, [])
  async function submit(event) {
    event.preventDefault()
    if (lock.current) return
    const message = projectNameError(name)
    setError(message); setRequestError(''); setSaved(false)
    if (message) { input.current?.focus(); return }
    lock.current = true; setBusy(true); controller.current = new AbortController()
    try {
      const updated = await adapter[project ? 'updateProject' : 'createProject']({ ...(project ? { projectId: project.id } : {}), name: name.trim(), signal: controller.current.signal })
      if (!updated || !/^[a-z0-9-]+$/.test(updated.id) || typeof updated.name !== 'string' || (project && updated.id !== project.id)) throw new Error('Unexpected project result')
      if (active.current) { onSaved(updated); setName(updated.name); setSaved(true) }
    } catch (err) {
      if (!active.current || err?.name === 'AbortError') return
      const kind = failureKind(err)
      if (['expired', 'forbidden', 'unavailable'].includes(kind)) setFailure(kind)
      else setRequestError(`Could not ${project ? 'save changes' : 'create the project'}. Try again.`)
    } finally { lock.current = false; if (active.current) setBusy(false) }
  }
  if (failure) return <AccessState kind={failure} target={project ? `/projects/${project.id}/settings` : '/projects'} />
  return <form className="project-form" noValidate onSubmit={submit} aria-busy={busy}>
    <div className="project-fields">
      <h2>{project ? 'General' : 'Project details'}</h2>
      <p className="section-description">{project ? 'The name shown in your project navigation.' : 'Choose a name that identifies your agent or application.'}</p>
      <div className="form-field"><label htmlFor="project-name">Project name</label><input ref={input} id="project-name" placeholder="e.g. Support agent" value={name} required readOnly={busy} onChange={e => { setName(e.target.value); setSaved(false) }} aria-invalid={!!error} aria-describedby={error ? 'project-error' : 'project-name-help'}/><p id="project-name-help" className="secondary">You can change this later.</p>{error && <p id="project-error" className="field-error" role="alert">{error}</p>}</div>
      {project && <dl className="project-identity"><dt>Project ID</dt><dd className="mono">{project.id}</dd></dl>}
      {requestError && <p className="form-error" role="alert">{requestError}</p>}
    </div>
    <div className="project-form-footer"><a className="button" href={project ? runsHref(project.id) : '#/projects'}>{project ? 'Back to Runs' : 'Cancel'}</a><button className="button solid" disabled={busy}>{busy ? project ? 'Saving…' : 'Creating…' : project ? 'Save changes' : 'Create project'}</button></div>
    <p role="status" className="project-save-status secondary">{busy ? project ? 'Saving changes…' : 'Creating project…' : saved ? 'Saved for this preview. Changes reset on reload.' : ''}</p>
  </form>
}

export default function ProjectsPage({ route, project, state, adapter }) {
  if (state.error) return <AccessState kind={state.error} retry={state.retry} target={route.path}/>
  if (state.busy) return <section className="project-page"><h1>Projects</h1><p role="status">Loading projects…</p></section>
  const creating = route.projectsPage === 'new'
  const canCreate = typeof adapter.createProject === 'function'
  const canUpdate = typeof adapter.updateProject === 'function'
  if ((creating && !canCreate) || (route.settings && project && !canUpdate)) return <AccessState kind="disconnected"/>
  if (route.settings && !project) return <AccessState kind="unavailable"/>
  return <section className="project-page">
    <div className="project-heading"><h1>{creating ? 'Create project' : project ? 'Project settings' : 'Projects'}</h1>{canCreate && !creating && !project && state.projects.length > 0 && <a className="button" href="#/projects/new">Create project</a>}</div>
    <p className="project-description secondary">{creating ? 'A dedicated place for your agent’s executions.' : project ? 'Manage your project’s name and identity.' : 'Your workspaces for agent debugging.'}</p>
    {creating || project ? <ProjectForm key={project?.id || 'new'} project={project} adapter={adapter} onSaved={updated => { state.accept(updated); if (!project) window.location.hash = runsHref(updated.id).slice(1) }}/>
      : state.projects.length ? <ul className="project-list" aria-label="Available projects">{state.projects.map(item => <li key={item.id}><a href={runsHref(item.id)}><span className="project-avatar" aria-hidden="true">{item.initial || item.name[0]}</span><span><strong>{item.name}</strong><span className="secondary mono">{item.id}</span></span></a>{canUpdate && <a className="button small" href={settingsHref(item.id)} aria-label={`Settings for ${item.name}`}>Settings</a>}</li>)}</ul>
        : <div className="project-empty"><span className="access-symbol" aria-hidden="true"><Icon name="branch"/></span><h2>Create your first project</h2><p className="secondary">Keep related executions and investigations together in one workspace.</p><a className="button solid" href="#/projects/new">Create project<Icon name="arrow"/></a></div>}
    <p className="development-notice">{adapter.mode === 'fixture' ? 'Development preview · Project changes reset on reload. No ownership or access is established.' : 'Project management is not connected. This local workspace identifies temporary SDK captures only.'}</p>
  </section>
}
