import { useSyncExternalStore } from 'react'

const subscribe = callback => { window.addEventListener('hashchange', callback); return () => window.removeEventListener('hashchange', callback) }
const snapshot = () => window.location.hash
export function parseRoute(hash) {
  const [path, search = ''] = (hash.replace(/^#/, '') || '/projects').split('?')
  // Public pages: no session needed. `#/` is the landing page, `#/docs/<page>` the docs.
  if (path === '/') return { landing: true, projectId: null, runId: null, search, path }
  const docs = /^\/docs(?:\/([a-z0-9-]+))?\/?$/.exec(path)
  if (docs) return { docs: docs[1] || 'introduction', projectId: null, runId: null, search, path }
  const account = /^\/account\/(login|register|session-expired|access-denied)$/.exec(path)
  if (account) return { account: account[1], projectId: null, runId: null, search, path }
  if (path === '/projects' || path === '/projects/new') return { projectsPage: path.endsWith('/new') ? 'new' : 'list', projectId: null, runId: null, search, path }
  const settings = /^\/projects\/([a-z0-9-]+)\/settings$/.exec(path)
  if (settings) return { settings: true, projectId: settings[1], runId: null, search, path }
  // There is no Profile page: the account lives in Settings › General. Old Profile URLs redirect there.
  if (path === '/profile' || /^\/projects\/[a-z0-9-]+\/profile$/.test(path)) return { profile: true, projectId: null, runId: null, search, path }
  // Project home. The former /setup page now lives on Home; old links still land there.
  const home = /^\/projects\/([a-z0-9-]+)(?:\/(?:home|setup))?$/.exec(path)
  if (home && home[1] !== 'new') return { home: true, projectId: home[1], runId: null, search, path }
  const match = /^\/projects\/([a-z0-9-]+)\/runs(?:\/(R-\d+|[0-9a-f]{32})(\/evidence)?)?$/.exec(path)
  return match ? { projectId: match[1], runId: match[2] || null, evidence: !!match[3], search, path } : { projectId: null, runId: null, search: '', path }
}
export const docsHref = (page = '') => `#/docs${page ? '/' + page : ''}`
export const isPublic = route => !!(route.landing || route.docs)
export const settingsHref = id => `#/projects/${encodeURIComponent(id)}/settings`
export const homeHref = id => `#/projects/${encodeURIComponent(id)}`
// Navigation allowlist only. A return target never proves session validity or access.
export function safeReturn(value) {
  if (typeof value !== 'string' || value.length > 2048 || /[\\\r\n]/.test(value)) return '/projects'
  const route = parseRoute('#' + value)
  return value.startsWith('/projects') && (route.projectId || route.projectsPage === 'list') ? value : '/projects'
}
export const accountHref = (page, target = '/projects') => `#/account/${page}?returnTo=${encodeURIComponent(safeReturn(target))}`
// Replace the current history entry (no Back loop through a redirect).
export function replaceHash(href) {
  window.history.replaceState(null, '', href)
  window.dispatchEvent(new HashChangeEvent('hashchange'))
}
// A data read got 401: the session is gone. Send the user to the session-expired
// page with a way back to where they were. Account pages never redirect again.
export function expireSession(hash = window.location.hash) {
  const route = parseRoute(hash)
  if (route.account) return
  replaceHash(accountHref('session-expired', route.path + (route.search ? '?' + route.search : '')))
}
export function runsHref(projectId, search = '', runId = null) { return `#/projects/${encodeURIComponent(projectId)}/runs${runId ? '/' + encodeURIComponent(runId) : ''}${search ? '?' + search : ''}` }
export function evidenceHref(projectId, runId, search = '') {
  return `${runsHref(projectId, '', runId)}/evidence${search ? '?' + search : ''}`
}
export function useRoute() { return parseRoute(useSyncExternalStore(subscribe, snapshot, () => '')) }
export function replaceQuery(projectId, search) {
  window.history.replaceState(null, '', runsHref(projectId, search))
  window.dispatchEvent(new HashChangeEvent('hashchange'))
}
