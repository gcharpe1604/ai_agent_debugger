export const traceKeys = ['span', 'spanSearch', 'spanType', 'spanStatus', 'loaded', 'panel', 'view', 'from', 'to', 'evidenceAttempt', 'evidenceFinding', 'evidenceA', 'evidenceB', 'evidenceFocus']
export function returnQuery(search) {
  const params = new URLSearchParams(search)
  traceKeys.forEach(key => params.delete(key))
  return params.toString()
}
export function initialTraceState(search, cached, mode) {
  const p = new URLSearchParams(search)
  const from = p.has('from') ? Number(p.get('from')) : NaN, to = p.has('to') ? Number(p.get('to')) : NaN
  return {
    collapsed: [], search: '', type: '', status: '', selected: null, active: null, open: false,
    mode, tab: 'Content', format: 'Readable', wrap: true, attributeSearch: '', scrollTop: 0, anchor: null,
    reading: {}, reveal: null, pending: null, notice: '', view: 'tree', timeWindow: null, ...cached,
    ...(p.has('view') ? { view: p.get('view') === 'timeline' ? 'timeline' : 'tree' } : {}),
    ...(p.has('from') || p.has('to') ? { timeWindow: Number.isFinite(from) && Number.isFinite(to) && to > from ? { start: from, end: to } : null } : {}),
    ...(p.has('span') ? { selected: p.get('span'), active: p.get('span'), open: p.get('panel') !== 'closed' } : {}),
    ...(p.has('spanSearch') ? { search: p.get('spanSearch') } : {}),
    ...(p.has('spanType') ? { type: p.get('spanType') } : {}),
    ...(p.has('spanStatus') ? { status: p.get('spanStatus') } : {}),
    ...(['overlay', 'pinned'].includes(p.get('panel')) ? { mode: p.get('panel') } : {}),
  }
}
export function traceReducer(state, action) {
  if (action.type === 'patch') return { ...state, ...action.value }
  if (action.type === 'toggle') return { ...state, collapsed: state.collapsed.includes(action.id) ? state.collapsed.filter(id => id !== action.id) : [...state.collapsed, action.id] }
  if (action.type === 'filter') return { ...state, ...action.value, reveal: null, scrollTop: 0, anchor: null }
  if (action.type === 'read-position') return { ...state, reading: { ...state.reading, [action.key]: action.top } }
  return state
}
