import { useCallback, useState } from 'react'

// Values kept for the life of the page only (not localStorage): a reload starts
// from the defaults again. Used for split-pane widths.
const values = new Map()

export function useSessionValue(key, fallback) {
  const [value, setValue] = useState(() => values.has(key) ? values.get(key) : fallback)
  const update = useCallback(next => { values.set(key, next); setValue(next) }, [key])
  return [value, update]
}

// Tests start each case from the defaults.
export function clearSessionValues() { values.clear() }
