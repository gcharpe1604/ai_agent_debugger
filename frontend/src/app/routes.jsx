import { useSyncExternalStore } from 'react'

const subscribe = callback => { window.addEventListener('hashchange', callback); return () => window.removeEventListener('hashchange', callback) }
const snapshot = () => window.location.hash
export function parseRoute(hash) {
  const [path, search = ''] = (hash.replace(/^#/, '') || '/projects/agent-examples/runs').split('?')
  const account = /^\/account\/(login|register|session-expired|access-denied)$/.exec(path)
  if (account) return { account: account[1], projectId: null, runId: null, search, path }
  if (path === '/projects' || path === '/projects/new') return { projectsPage: path.endsWith('/new') ? 'new' : 'list', projectId: null, runId: null, search, path }
  const settings = /^\/projects\/([a-z0-9-]+)\/settings$/.exec(path)
  if (settings) return { settings: true, projectId: settings[1], runId: null, search, path }
  const match = /^\/projects\/([a-z0-9-]+)\/runs(?:\/(R-\d+)(\/evidence)?)?$/.exec(path)
  return match ? { projectId: match[1], runId: match[2] || null, evidence: !!match[3], search, path } : { projectId: null, runId: null, search: '', path }
}
export const settingsHref = id => `#/projects/${encodeURIComponent(id)}/settings`
// Navigation allowlist only. A return target never proves session validity or access.
export function safeReturn(value) {
  if (typeof value !== 'string' || value.length > 2048 || /[\\\r\n]/.test(value)) return '/projects'
  const route = parseRoute('#' + value)
  return value.startsWith('/projects') && (route.projectId || route.projectsPage === 'list') ? value : '/projects'
}
export const accountHref = (page, target = '/projects') => `#/account/${page}?returnTo=${encodeURIComponent(safeReturn(target))}`
export function runsHref(projectId, search = '', runId = null) { return `#/projects/${encodeURIComponent(projectId)}/runs${runId ? '/' + encodeURIComponent(runId) : ''}${search ? '?' + search : ''}` }
export function evidenceHref(projectId, runId, search = '') {
  return `${runsHref(projectId, '', runId)}/evidence${search ? '?' + search : ''}`
}
export function useRoute() { return parseRoute(useSyncExternalStore(subscribe, snapshot, () => '')) }
export function replaceQuery(projectId, search) {
  window.history.replaceState(null, '', runsHref(projectId, search))
  window.dispatchEvent(new HashChangeEvent('hashchange'))
}
