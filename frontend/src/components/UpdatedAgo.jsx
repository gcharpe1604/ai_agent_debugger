import { useEffect, useState } from 'react'
import { agoText } from '../app/format.js'

// Re-renders its own label every 10 s. It never reads data; Refresh does.
export default function UpdatedAgo({ at }) {
  const [now, setNow] = useState(() => Date.now())
  // A clock older than `at` reads as "just now" (agoText clamps at zero).
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 10000)
    return () => clearInterval(timer)
  }, [at])
  if (!Number.isFinite(at)) return null
  return <time className="updated-ago" dateTime={new Date(at).toISOString()} title={`Last read ${new Date(at).toLocaleString()}`}>{agoText(at, now)}</time>
}
