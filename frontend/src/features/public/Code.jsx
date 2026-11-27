import { Fragment, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/Tabs.jsx'

// A small highlighter for the three landing snippets: comments, strings and a
// fixed keyword list. Not a parser; good enough for code we wrote ourselves.
const KEYWORDS = new Set(['from', 'import', 'with', 'as', 'class', 'def', 'return', 'lambda', 'pip', 'install'])
const TOKEN = /("(?:[^"\\]|\\.)*"?)|(#.*$)|([A-Za-z_]\w*)|([^"#A-Za-z_]+)/g

function tokens(line, language) {
  if (language === 'env') {
    const equals = line.indexOf('=')
    return equals < 0 ? [[line, null]] : [[line.slice(0, equals), 'key'], ['=', 'muted'], [line.slice(equals + 1), 'string']]
  }
  return [...line.matchAll(TOKEN)].map(([text, string, comment, word]) => [text, string ? 'string' : comment ? 'muted' : word && KEYWORDS.has(word) ? 'key' : null])
}

// A break opportunity after every '/', '#' and '=', so the install command wraps
// at path boundaries instead of mid-word.
const breakable = text => text.split(/(?<=[/#=])/).map((part, index, parts) => <Fragment key={index}>{part}{index < parts.length - 1 && <wbr/>}</Fragment>)

export function Highlighted({ text, language, wrapPaths = false }) {
  return tokens(text, language).map(([part, kind], index) => {
    const content = wrapPaths ? breakable(part) : part
    return kind ? <span key={index} className={`lp-tok-${kind}`}>{content}</span> : <Fragment key={index}>{content}</Fragment>
  })
}

function Lines({ text, language }) {
  return <pre className="lp-lines"><code>
    {text.split('\n').map((line, index) => <span key={index} className="lp-line">
      <span className="lp-ln" aria-hidden="true">{index + 1}</span>
      <span className="lp-lt">{line ? <Highlighted text={line} language={language} wrapPaths={language === 'shell'}/> : <br/>}</span>
    </span>)}
  </code></pre>
}

export function CopyButton({ text, label }) {
  const [notice, setNotice] = useState('')
  async function copy() {
    try { await navigator.clipboard.writeText(text); setNotice(`${label} copied`) }
    catch { setNotice('Clipboard unavailable. Select the text and copy it.') }
  }
  return <>
    <button type="button" className="lp-copy" aria-label={`Copy ${label}`} title={`Copy ${label}`} onClick={copy}><Icon name="copy"/></button>
    <span className="sr-only" aria-live="polite">{notice}</span>
  </>
}

// Tabs of code that copy their raw text. `tabs`: [{ id, label, language, text }].
export function CodeCard({ tabs }) {
  const [active, setActive] = useState(tabs[0].id)
  const current = tabs.find(tab => tab.id === active)
  return <Tabs value={active} onValueChange={setActive} className="lp-card">
    <div className="lp-card-head">
      <TabsList className="lp-tabs" aria-label="Setup code">
        {tabs.map(tab => <TabsTrigger key={tab.id} value={tab.id} className="lp-tab">{tab.label}</TabsTrigger>)}
      </TabsList>
      <CopyButton text={current.text} label={current.label}/>
    </div>
    {tabs.map(tab => <TabsContent key={tab.id} value={tab.id} className="lp-card-body"><Lines text={tab.text} language={tab.language}/></TabsContent>)}
  </Tabs>
}
