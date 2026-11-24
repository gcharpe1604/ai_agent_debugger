import { useEffect, useState } from 'react'
import { agoText, formatTimestamp } from '../app/format.js'

// Re-renders its own label every 10 s. It never reads data; Refresh does.
export default function UpdatedAgo({ at }) {
  const [now, setNow] = useState(() => Date.now())
  // A clock older than `at` reads as "just now" (agoText clamps at zero).
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 10000)
    return () => clearInterval(timer)
  }, [at])
  if (!Number.isFinite(at)) return null
  const iso = new Date(at).toISOString()
  return <time className="updated-ago" dateTime={iso} title={`Last read ${formatTimestamp(iso)} (${iso})`}>{agoText(at, now)}</time>
}
