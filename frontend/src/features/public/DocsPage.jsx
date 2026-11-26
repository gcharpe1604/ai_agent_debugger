import { useEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { docsHref } from '../../app/routes.jsx'
import { docGroups, docOrder, docPages } from './docsIndex.js'

// "On this page": headings are read from the rendered article. Links use buttons,
// because a #fragment would be read as a route by the hash router.
function Contents({ article, page }) {
  const [headings, setHeadings] = useState([])
  useEffect(() => {
    // Read after the new article has rendered, not during the commit.
    const frame = requestAnimationFrame(() => setHeadings([...(article.current?.querySelectorAll('h2[id]') || [])].map(node => [node.id, node.textContent])))
    return () => cancelAnimationFrame(frame)
  }, [article, page])
  if (headings.length < 3) return null
  return <nav className="docs-contents" aria-label="On this page">
    <p className="docs-nav-heading">On this page</p>
    <ul>{headings.map(([id, text]) => <li key={id}><button type="button" onClick={() => { const node = document.getElementById(id); node?.scrollIntoView({ block: 'start' }); node?.focus({ preventScroll: true }) }}>{text}</button></li>)}</ul>
  </nav>
}

function Sidebar({ page }) {
  return <nav className="docs-sidebar" aria-label="Docs">
    {docGroups.map(([group, slugs]) => <div key={group} className="docs-nav-group">
      <p className="docs-nav-heading">{group}</p>
      <ul>{slugs.map(slug => <li key={slug}><a href={docsHref(slug)} aria-current={slug === page ? 'page' : undefined}>{docPages[slug].title}</a></li>)}</ul>
    </div>)}
  </nav>
}

export default function DocsPage({ page }) {
  const entry = docPages[page]
  const article = useRef(null)
  const index = docOrder.indexOf(page)
  const previous = index > 0 ? docOrder[index - 1] : null
  const following = index >= 0 && index < docOrder.length - 1 ? docOrder[index + 1] : null
  useEffect(() => {
    document.title = `${entry ? entry.title : 'Page not found'} · Agent Debugger docs`
    window.scrollTo(0, 0)
  }, [entry])
  return <div className="docs-layout">
    {/* Small screens: the sidebar folds into a disclosure above the article. */}
    <details className="docs-mobile-nav">
      <summary>{entry ? entry.title : 'Docs'}<Icon name="chevron-down"/></summary>
      <Sidebar page={page}/>
    </details>
    <Sidebar page={page}/>
    <article className="docs-article" ref={article} aria-labelledby="docs-title">
      {entry ? <>
        <p className="docs-kicker">{docGroups.find(([, slugs]) => slugs.includes(page))[0]}</p>
        <h1 id="docs-title">{entry.title}</h1>
        <div className="docs-body"><entry.Body/></div>
        <nav className="docs-pager" aria-label="Previous and next page">
          {previous ? <a href={docsHref(previous)} className="docs-pager-link"><span>Previous</span><strong><Icon name="back"/>{docPages[previous].title}</strong></a> : <span/>}
          {following && <a href={docsHref(following)} className="docs-pager-link next"><span>Next</span><strong>{docPages[following].title}<Icon name="arrow"/></strong></a>}
        </nav>
      </> : <>
        <h1 id="docs-title">Page not found</h1>
        <p className="docs-lede">There is no docs page called <code className="inline-code">{page}</code>. <a href={docsHref()}>Start with the introduction</a>.</p>
      </>}
    </article>
    {entry && <Contents article={article} page={page}/>}
  </div>
}
