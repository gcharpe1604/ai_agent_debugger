import { useState } from 'react'
import Icon from './Icon.jsx'
import './copyBlock.css'

export default function CopyBlock({ label, text }) {
  const [notice, setNotice] = useState('')
  async function copy() {
    try { await navigator.clipboard.writeText(text); setNotice(`${label} copied`) }
    catch { setNotice('Clipboard unavailable. Select the text and copy it.') }
  }
  return <div className="copy-block">
    <div className="copy-block-header"><span>{label}</span><button type="button" className="button small" onClick={copy} aria-label={`Copy ${label}`}><Icon name="copy"/>Copy</button></div>
    <pre><code>{text}</code></pre>
    <span className="sr-only" aria-live="polite">{notice}</span>
  </div>
}
