import { formatTimestamp, timestampTitle } from '../app/format.js'

// Local "24 Nov, 11:41:18" with the full UTC ISO time on hover.
export default function Timestamp({ value, withSeconds = true, fallback = 'Unknown', className }) {
  const text = formatTimestamp(value, { withSeconds })
  if (!text) return <span className={className}>{fallback}</span>
  const iso = timestampTitle(value)
  // HTML datetime allows at most milliseconds; the title keeps every digit.
  return <time className={className} dateTime={iso.replace(/(\.\d{3})\d+Z$/, '$1Z')} title={iso}>{text}</time>
}
