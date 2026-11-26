import { useState } from 'react'
import Icon from '../../components/Icon.jsx'

// A small collapsible JSON viewer. Objects and arrays fold; arrays over 10 items
// and strings over 400 characters start shortened with "Show more". Values are
// rendered as text only, never as HTML.
export const ARRAY_PREVIEW = 10
export const STRING_PREVIEW = 400
// Nodes deeper than this start folded.
const OPEN_DEPTH = 3

export function StringValue({ value, quoted = true }) {
  const [full, setFull] = useState(false)
  const long = value.length > STRING_PREVIEW
  const text = long && !full ? value.slice(0, STRING_PREVIEW) : value
  // Quotes come from CSS, so the element's text is exactly the value.
  return <><span className={quoted ? 'json-string quoted' : 'json-string'}>{text}{long && !full && '…'}</span>{long && <button type="button" className="json-more" onClick={() => setFull(!full)}>{full ? 'Show less' : `Show more (${(value.length - STRING_PREVIEW).toLocaleString('en')} characters)`}</button>}</>
}

function Scalar({ value }) {
  if (typeof value === 'string') return <StringValue value={value}/>
  if (typeof value === 'number') return <span className="json-number">{String(value)}</span>
  if (typeof value === 'boolean') return <span className="json-boolean">{String(value)}</span>
  if (value === null) return <span className="json-null">null</span>
  return <span className="json-null">{JSON.stringify(value) ?? 'Not recorded'}</span>
}

function Node({ name, value, depth, last }) {
  const branch = value !== null && typeof value === 'object'
  const isArray = Array.isArray(value)
  const entries = branch ? (isArray ? value.map((item, index) => [index, item]) : Object.entries(value).filter(([, item]) => item !== undefined)) : []
  const [open, setOpen] = useState(depth < OPEN_DEPTH)
  const [all, setAll] = useState(false)
  const key = name === undefined ? null : <><span className="json-key">{typeof name === 'number' ? name : `"${name}"`}</span><span className="json-punct">: </span></>
  const comma = last ? null : <span className="json-punct">,</span>
  if (!branch || !entries.length) return <div className="json-line" style={{ '--json-depth': depth }}>{key}{branch ? <span className="json-punct">{isArray ? '[]' : '{}'}</span> : <Scalar value={value}/>}{comma}</div>
  const [start, end] = isArray ? ['[', ']'] : ['{', '}']
  const summary = isArray ? `${entries.length} ${entries.length === 1 ? 'item' : 'items'}` : `${entries.length} ${entries.length === 1 ? 'key' : 'keys'}`
  const shown = isArray && !all && entries.length > ARRAY_PREVIEW ? entries.slice(0, ARRAY_PREVIEW) : entries
  const label = name === undefined ? 'value' : String(name)
  return <div className="json-node">
    <div className="json-line" style={{ '--json-depth': depth }}>
      <button type="button" className="json-toggle" aria-expanded={open} aria-label={`${open ? 'Collapse' : 'Expand'} ${label}`} onClick={() => setOpen(!open)}><Icon name="chevron"/></button>
      {key}<span className="json-punct">{start}</span>{!open && <><span className="json-summary">{summary}</span><span className="json-punct">{end}</span>{comma}</>}
    </div>
    {open && <>
      {shown.map(([childName, child], position) => <Node key={childName} name={childName} value={child} depth={depth + 1} last={position === entries.length - 1}/>)}
      {shown.length < entries.length && <div className="json-line" style={{ '--json-depth': depth + 1 }}><button type="button" className="json-more" onClick={() => setAll(true)}>Show {entries.length - shown.length} more {entries.length - shown.length === 1 ? 'item' : 'items'}</button></div>}
      <div className="json-line" style={{ '--json-depth': depth }}><span className="json-punct">{end}</span>{comma}</div>
    </>}
  </div>
}

// A top-level string is shown as text (no quotes), still shortened when long.
export default function JsonView({ value }) {
  return <div className="json-view" role="group" aria-label="JSON value">
    {typeof value === 'string' ? <div className="json-text"><StringValue value={value} quoted={false}/></div> : <Node value={value} depth={0} last/>}
  </div>
}
