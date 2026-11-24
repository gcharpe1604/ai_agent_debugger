import Icon from './Icon.jsx'

// GitHub-style status: a filled coloured icon before plain text. Completed and
// OK get a green check, Failed and ERROR a red cross, Partial an amber mark;
// anything else a grey dashed circle.
const kinds = { Completed: 'ok', OK: 'ok', ok: 'ok', Failed: 'error', ERROR: 'error', error: 'error', Partial: 'warning' }
const statusKind = state => kinds[state] || 'unknown'

export default function StatusLabel({ state, children }) {
  const kind = statusKind(state)
  return <span className="status-label" data-kind={kind}><Icon name={`status-${kind}`}/>{children ?? state}</span>
}
