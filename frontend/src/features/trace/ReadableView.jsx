import { useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { ARRAY_PREVIEW, StringValue } from './JsonView.jsx'

// The Formatted view of a captured value: a field/value table instead of JSON
// syntax. Strings read as plain text (no quotes or escapes), objects and lists
// become nested tables that fold, lists over 10 items start shortened. Values
// are rendered as text only, never as HTML.
const OPEN_DEPTH = 2
const isBranch = value => value !== null && typeof value === 'object'
const plural = (count, one, many) => `${count.toLocaleString('en')} ${count === 1 ? one : many}`

function Scalar({ value }) {
  if (typeof value === 'string') return value === '' ? <span className="readable-empty">Empty text</span> : <span className="readable-text"><StringValue value={value} quoted={false}/></span>
  if (typeof value === 'number') return <span className="json-number">{String(value)}</span>
  if (typeof value === 'boolean') return <span className="json-boolean">{String(value)}</span>
  if (value === null) return <span className="readable-empty">null</span>
  return <span className="readable-empty">{JSON.stringify(value) ?? 'undefined'}</span>
}

// A list of plain values reads as one stacked list, not numbered rows.
function ScalarList({ items }) {
  const [all, setAll] = useState(false)
  const shown = !all && items.length > ARRAY_PREVIEW ? items.slice(0, ARRAY_PREVIEW) : items
  return <ul className="readable-list">
    {shown.map((item, index) => <li key={index}><Scalar value={item}/></li>)}
    {shown.length < items.length && <li><button type="button" className="json-more" onClick={() => setAll(true)}>Show {plural(items.length - shown.length, 'more item', 'more items')}</button></li>}
  </ul>
}

function Field({ name, value, depth }) {
  const branch = isBranch(value)
  const list = Array.isArray(value)
  const count = branch ? (list ? value.length : Object.keys(value).length) : 0
  const [open, setOpen] = useState(depth < OPEN_DEPTH)
  const label = String(name)
  if (!branch || !count) return <div className="readable-row"><dt>{label}</dt><dd>{branch ? <span className="readable-empty">{list ? 'Empty list' : 'No fields'}</span> : <Scalar value={value}/>}</dd></div>
  if (list && !value.some(isBranch)) return <div className="readable-row"><dt>{label}</dt><dd><ScalarList items={value}/></dd></div>
  return <div className="readable-row readable-branch" data-open={open || undefined}>
    <dt><button type="button" className="readable-toggle" aria-expanded={open} aria-label={`${open ? 'Collapse' : 'Expand'} ${label}`} onClick={() => setOpen(!open)}><Icon name="chevron"/><span>{label}</span></button></dt>
    <dd>{open ? <Fields value={value} depth={depth + 1}/> : <span className="readable-summary">{list ? plural(count, 'item', 'items') : plural(count, 'field', 'fields')}</span>}</dd>
  </div>
}

function Fields({ value, depth }) {
  const list = Array.isArray(value)
  const entries = list ? value.map((item, index) => [index, item]) : Object.entries(value)
  const [all, setAll] = useState(false)
  const shown = list && !all && entries.length > ARRAY_PREVIEW ? entries.slice(0, ARRAY_PREVIEW) : entries
  return <dl className="readable-fields">
    {shown.map(([name, item]) => <Field key={name} name={name} value={item} depth={depth}/>)}
    {shown.length < entries.length && <div className="readable-row"><dt/><dd><button type="button" className="json-more" onClick={() => setAll(true)}>Show {plural(entries.length - shown.length, 'more item', 'more items')}</button></dd></div>}
  </dl>
}

export default function ReadableView({ value }) {
  const empty = isBranch(value) && !(Array.isArray(value) ? value.length : Object.keys(value).length)
  return <div className="readable-view" role="group" aria-label="Formatted value">
    {!isBranch(value) ? <div className="readable-scalar"><Scalar value={value}/></div>
      : empty ? <span className="readable-empty">{Array.isArray(value) ? 'Empty list' : 'No fields'}</span>
        : Array.isArray(value) && !value.some(isBranch) ? <div className="readable-scalar"><ScalarList items={value}/></div>
          : <Fields value={value} depth={0}/>}
  </div>
}
