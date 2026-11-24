// Tree view columns by priority. Name (with its status dot) and Duration never
// go; below 640 px of tree width Start offset and Type go first, and the
// optional Span ID column needs 840 px.
export const TREE_MIN_WIDTH = 420
export const INSPECTOR_MIN_WIDTH = 360
const fixed = { id: '150px', start: '76px', type: '84px' }

export function treeColumns(width, { showIds = false } = {}) {
  const columns = ['name']
  if (showIds && width >= 840) columns.push('id')
  if (width >= 640) columns.push('start', 'type')
  columns.push('duration')
  return columns
}

// CSS grid template for the columns above. The duration column holds the
// waterfall bar and the value, so it narrows on small trees.
export function treeGridTemplate(columns, width) {
  return columns.map(column => column === 'name' ? 'minmax(0,1fr)' : column === 'duration' ? (width >= 520 ? '176px' : '120px') : fixed[column]).join(' ')
}
