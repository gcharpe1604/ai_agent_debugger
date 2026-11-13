import { useState, useEffect, useSyncExternalStore } from 'react'

const prefix = 'agent-debugger.frontend.v1.'
// `allowed` is a list of accepted values or a predicate for open-ended ones
// (for example a comma-separated column list). Stored values are re-checked on read.
const accepts = (allowed, value) => typeof value === 'string' && (typeof allowed === 'function' ? allowed(value) : allowed.includes(value))
export function readPreference(key, allowed, fallback) {
  try { const value = localStorage.getItem(prefix + key); return accepts(allowed, value) ? value : fallback } catch { return fallback }
}
export function writePreference(key, value) {
  try { localStorage.setItem(prefix + key, value) } catch { /* Presentation works without persistent storage. */ }
}
export function usePreference(key, allowed, fallback) {
  const [value, setValue] = useState(() => readPreference(key, allowed, fallback))
  function update(next) { if (accepts(allowed, next)) { setValue(next); writePreference(key, next) } }
  return [value, update]
}
const media = () => window.matchMedia('(prefers-color-scheme: dark)')
const subscribe = callback => { const query = media(); query.addEventListener('change', callback); return () => query.removeEventListener('change', callback) }
const snapshot = () => media().matches
export function useTheme() {
  const [preference, setPreference] = usePreference('theme', ['light', 'dark', 'system'], 'system')
  const systemDark = useSyncExternalStore(subscribe, snapshot, () => false)
  const resolved = preference === 'system' ? systemDark ? 'dark' : 'light' : preference
  useEffect(() => { document.documentElement.dataset.theme = resolved; document.documentElement.style.colorScheme = resolved }, [resolved])
  return { preference, setPreference, resolved }
}
