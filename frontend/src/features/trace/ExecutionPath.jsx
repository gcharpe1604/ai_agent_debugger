import { Fragment } from 'react'
import Icon from '../../components/Icon.jsx'

// One-line summary of the run's top-level steps in recorded start order.
// Routing spans render as the arrow between steps; a repeated step is marked
// so loops and retries stand out. Clicking a step selects that span.
export default function ExecutionPath({ path, selected, select }) {
  if (!path.steps.length) return null
  return <nav className="execution-path" aria-label="Execution path">
    <span className="execution-path-label">Path</span>
    <ol>
      {path.steps.map((step, position) => <Fragment key={step.id}>
        {position > 0 && !step.decision && !path.steps[position - 1].decision && <li className="path-arrow" aria-hidden="true"><Icon name="arrow"/></li>}
        {step.decision
          ? <li className="path-decision"><button type="button" data-inspector-trigger aria-pressed={selected === step.id} title={`Routing decision after ${step.label}. Open span ${step.id}.`} aria-label={`Routing decision after ${step.label}`} onClick={() => select(step.id)}><Icon name="arrow"/></button></li>
          : <li><button type="button" className="path-step" data-inspector-trigger data-type={step.type} data-error={step.error || undefined} aria-pressed={selected === step.id} title={`${step.label}${step.repeat ? ' · repeated step' : ''}${step.error ? ' · ERROR' : ''} · span ${step.id}`} onClick={() => select(step.id)}>
            {step.repeat && <Icon name="retry"/>}{step.label}
          </button></li>}
      </Fragment>)}
      {path.hidden > 0 && <li className="path-more">+{path.hidden} more in the tree</li>}
    </ol>
  </nav>
}
