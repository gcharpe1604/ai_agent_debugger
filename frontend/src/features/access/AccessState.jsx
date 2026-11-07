import { useEffect, useRef } from 'react'
import { accountHref } from '../../app/routes.jsx'
import Icon from '../../components/Icon.jsx'

const states = {
  expired: ['Session expired', 'Sign in again to return to your workspace.'],
  forbidden: ['Access denied', 'You don’t have access to this workspace. Choose another project or contact its owner.'],
  unavailable: ['Project unavailable', 'The requested project could not be opened. Choose an available project.'],
  failure: ['Could not load projects', 'The project request failed. Retry the request.'],
  disconnected: ['Project service unavailable', 'Project management is not connected. Start the backend and frontend to inspect SDK executions captured by the local backend.'],
}
export default function AccessState({ kind, target, retry }) {
  const [title, description] = states[kind] || states.failure
  const heading = useRef(null)
  useEffect(() => { heading.current?.focus() }, [kind])
  return <section className="access-state" aria-labelledby="access-heading">
    <span className="access-symbol" aria-hidden="true"><Icon name={kind === 'expired' ? 'clock' : kind === 'forbidden' ? 'lock' : 'error'}/></span>
    <h1 id="access-heading" ref={heading} tabIndex="-1" aria-describedby="access-description">{title}</h1><p id="access-description" className="secondary">{description}</p>
    <div className="form-actions">
      {kind === 'expired' ? <a className="button solid" href={accountHref('login', target)}>Sign in</a>
        : retry && <button className="button solid" onClick={retry}>Retry</button>}
      <a className={`button ${kind !== 'expired' && !retry ? 'solid' : ''}`} href="#/projects">Choose project</a>
    </div>
  </section>
}
