import { JsonValue } from '../trace/Payload.jsx'

const samePath = (a, b) => Array.isArray(b) && a.length === b.length && a.every((part, i) => part === b[i])
function Readable({ value, target, path = [] }) {
  if (!value || typeof value !== 'object' || !Object.keys(value).length) {
    const text = typeof value === 'string' ? value : JSON.stringify(value)
    return samePath(path, target) ? <mark>{text}</mark> : <span>{text}</span>
  }
  return <dl className="evidence-fields">{Object.entries(value).map(([key, item]) => <div key={key}><dt className="mono">{key}</dt><dd><Readable value={item} target={target} path={[...path, Array.isArray(value) ? Number(key) : key]}/></dd></div>)}</dl>
}
// Generate lines from the captured structure, binding highlights to exact paths,
// never a substring match that could highlight another occurrence of the value.
function jsonLines(value, target, path = [], indent = 0, prefix = '', comma = '') {
  const pad = ' '.repeat(indent), hit = samePath(path, target)
  if (value === null || typeof value !== 'object' || !Object.keys(value).length) return [{ text: pad + prefix + JSON.stringify(value) + comma, hit }]
  const array = Array.isArray(value), entries = Object.entries(value)
  return [{ text: pad + prefix + (array ? '[' : '{'), hit }, ...entries.flatMap(([key, item], i) => jsonLines(item, target, [...path, array ? Number(key) : key], indent + 2, array ? '' : JSON.stringify(key) + ': ', i < entries.length - 1 ? ',' : '')), { text: pad + (array ? ']' : '}') + comma, hit }]
}
export default function CapturedEvidence({ source, citation, resolved, format }) {
  if (typeof source.value === 'string') {
    const range = resolved && citation.range
    if (format === 'JSON') {
      if (!range) return <JsonValue value={source.value}/>
      const encoded = JSON.stringify(source.value), start = 1 + JSON.stringify(source.value.slice(0, range.start)).length - 2
      const length = JSON.stringify(source.value.slice(range.start, range.end)).length - 2
      return <pre className="captured-json wrap"><code>{encoded.slice(0, start)}<mark>{encoded.slice(start, start + length)}</mark>{encoded.slice(start + length)}</code></pre>
    }
    return <div className="readable-prose evidence-passage">{range ? <p>{source.value.slice(0, range.start)}<mark>{source.value.slice(range.start, range.end)}</mark>{source.value.slice(range.end)}</p> : <p>{source.value}</p>}</div>
  }
  const target = resolved ? citation.path || [] : null
  return format === 'JSON' ? <pre className="captured-json wrap evidence-json"><code>{jsonLines(source.value, target).map((line, index) => <span className="evidence-json-line" key={index}>{line.hit ? <mark>{line.text || ' '}</mark> : line.text}{'\n'}</span>)}</code></pre> : <Readable value={source.value} target={target}/>
}
