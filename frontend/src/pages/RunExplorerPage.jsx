import { useCallback, useEffect, useMemo, useRef } from 'react'
import AppShell from '../components/AppShell.jsx'
import Icon from '../components/Icon.jsx'
import UpdatedAgo from '../components/UpdatedAgo.jsx'
import RunTable from '../features/runs/RunTable.jsx'
import RunToolbar from '../features/runs/RunToolbar.jsx'
import FacetSidebar from '../features/runs/FacetSidebar.jsx'
import TracePeek from '../features/runs/TracePeek.jsx'
import { ColumnMenu, DensityMenu } from '../features/runs/TableControls.jsx'
import { useRuns } from '../features/runs/useRuns.js'
import { changeQuery, parseQuery, queryString } from '../features/runs/query.js'
import { densityValues, isHiddenColumnList, runColumns } from '../features/runs/runColumns.js'
import { useElementSize } from '../features/trace/useElementSize.js'
import { downloadTraceList } from '../features/trace/download.js'
import { homeHref, replaceQuery } from '../app/routes.jsx'
import { usePreference } from '../app/preferences.js'
import { hasModifier, isTyping } from '../app/keyboard.js'

const narrowScreen = () => typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 767px)').matches
const PEEK_ID = /^(?:[0-9a-f]{32}|R-\d+)$/
const PEEK_MIN = 480
const isPeekWidth = value => value === 'auto' || (/^\d{3,4}$/.test(value) && Number(value) >= PEEK_MIN && Number(value) <= 2400)

export default function RunExplorerPage({ project, projects, route, repository, traceRepository }) {
  const live = project.dataSource === 'local'
  // Open by default on wide screens; on phones the table comes first. A saved choice wins.
  const [filters, setFilters] = usePreference('traces.filters', ['open', 'closed'], narrowScreen() ? 'closed' : 'open')
  const [density, setDensity] = usePreference('traces.density', densityValues, 'medium')
  const [hiddenPreference, setHiddenPreference] = usePreference('traces.columns.hidden', isHiddenColumnList, '')
  const [peekWidthPreference, setPeekWidth] = usePreference('peek.width', isPeekWidth, 'auto')
  const hidden = useMemo(() => hiddenPreference ? hiddenPreference.split(',') : [], [hiddenPreference])
  // The previewed trace lives in the URL (peek=) but not in the list query, so
  // opening or stepping through previews never re-reads the list.
  const peekParam = new URLSearchParams(route.search).get('peek')
  const peek = PEEK_ID.test(peekParam || '') ? peekParam : null
  const listSearch = useMemo(() => { const params = new URLSearchParams(route.search); params.delete('peek'); return params.toString() }, [route.search])
  const query = useMemo(() => ({ ...parseQuery(listSearch), ...(live ? { time: 'all' } : {}) }), [listSearch, live])
  const key = queryString(query)
  const { result, loadedAt, error, busy, refresh } = useRuns(repository, project.id, query, key)
  const write = useCallback((search, peekId) => { const params = new URLSearchParams(search); if (peekId) params.set('peek', peekId); replaceQuery(project.id, params.toString()) }, [project.id])
  const change = patch => write(queryString(changeQuery(query, patch)), peek)
  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.pageSize)) : 1
  const canPrevious = !busy && result && result.page > 1
  const canNext = !busy && result && result.page < totalPages
  const showFilters = live && filters === 'open'
  // The toggle that was used disappears (Show lives in the toolbar, Hide in the
  // panel), so keyboard focus moves to its counterpart.
  const toggled = useRef(false)
  useEffect(() => {
    if (!toggled.current) return
    toggled.current = false
    document.getElementById(showFilters ? 'hide-filters' : 'show-filters')?.focus()
  }, [showFilters])
  function toggleFilters() { toggled.current = true; setFilters(showFilters ? 'closed' : 'open') }

  // Trace preview: J/K step through the rows on this page, Esc closes and
  // returns focus to that row's preview button.
  const items = useMemo(() => result?.items || [], [result])
  const peekIndex = peek ? items.findIndex(run => run.id === peek) : -1
  const openPeek = useCallback(id => write(key, id), [write, key])
  const previous = useMemo(() => peekIndex > 0 ? () => openPeek(items[peekIndex - 1].id) : null, [peekIndex, items, openPeek])
  const next = useMemo(() => peekIndex >= 0 && peekIndex < items.length - 1 ? () => openPeek(items[peekIndex + 1].id) : null, [peekIndex, items, openPeek])
  const closePeek = useCallback(() => {
    // The row's button exists with or without the panel, so focus moves before it closes.
    document.querySelector(`.row-peek[data-peek-id="${peek}"]`)?.focus()
    write(key, null)
  }, [peek, write, key])
  useEffect(() => {
    if (!peek) return
    function keys(event) {
      if (event.defaultPrevented || hasModifier(event) || isTyping(event.target)) return
      if (event.key === 'Escape') { event.preventDefault(); closePeek() }
      else if (event.key === 'j' || event.key === 'J') { if (next) { event.preventDefault(); next() } }
      else if (event.key === 'k' || event.key === 'K') { if (previous) { event.preventDefault(); previous() } }
    }
    document.addEventListener('keydown', keys)
    return () => document.removeEventListener('keydown', keys)
  }, [peek, next, previous, closePeek])
  const layout = useRef(null)
  const layoutSize = useElementSize(layout)
  const peekMax = Math.max(PEEK_MIN, Math.floor(layoutSize.width - 120))
  const peekWidth = Math.min(peekMax, Math.max(PEEK_MIN, peekWidthPreference === 'auto' ? Math.min(760, layoutSize.width * 0.55) : Number(peekWidthPreference)))

  const actions = <>
    {!busy && <UpdatedAgo at={loadedAt}/>}
    <button className="button small" onClick={refresh} disabled={busy} title="Read the latest captured traces"><Icon name="refresh"/><span className="button-label">{busy && result ? 'Refreshing…' : 'Refresh'}</span></button>
    <button className="button small" disabled={!items.length} onClick={() => downloadTraceList({ projectId: project.id, query, result })} title="Download the trace summaries on this page as JSON"><Icon name="download"/><span className="button-label">Download JSON</span></button>
  </>
  return <AppShell projects={projects} project={project} route={route} actions={actions}>
    <section className="explorer" data-source={live ? 'local' : undefined} aria-labelledby="runs-heading">
      <div className="view-heading">
        <h1 id="runs-heading">Tracing</h1>
        <span className="heading-info" title="Each trace is one agent run. Click a row to preview it; open it for the full span view."><Icon name="info"/><span className="sr-only">Each trace is one agent run. Click a row to preview it; open it for the full span view.</span></span>
      </div>
      <RunToolbar live={live} query={query} onChange={change} onReset={() => replaceQuery(project.id, '')} filtersOpen={showFilters} toggleFilters={toggleFilters}>
        <ColumnMenu columns={runColumns(items)} hidden={hidden} onChange={list => setHiddenPreference(list.join(','))}/>
        <DensityMenu density={density} onChange={setDensity}/>
      </RunToolbar>
      <div className={`traces-layout${showFilters ? ' with-filters' : ''}`} ref={layout}>
        {showFilters && <div id="trace-filters"><FacetSidebar query={query} facets={result?.facets} onChange={change} onClose={toggleFilters}/></div>}
        <div className="runs-ledger">
          {error && <div className="read-error" role="alert"><Icon name="error"/><div><strong>Could not load traces</strong><p>{error}{result ? ' Previously loaded data is shown.' : ''}</p></div><button className="button small" onClick={refresh}>Retry</button></div>}
          <div className="sr-only" role="status" aria-live="polite">{busy ? result ? 'Refreshing traces' : 'Loading traces' : error ? 'Trace read failed' : `${result?.total || 0} captured traces. Page ${result?.page || 1} of ${totalPages}.`}</div>
          <RunTable live={live} items={items} projectId={project.id} search={key} query={query} onSort={sort => change({ sort, direction: query.sort === sort && query.direction === 'asc' ? 'desc' : 'asc' })} busy={busy} hidden={hidden} density={density} peek={peek} onPeek={traceRepository ? openPeek : undefined}>
            {!result ? <div className="state-region">{busy ? <><span className="secondary">Loading traces…</span><div className="loading-rows" aria-hidden="true">{[0, 1, 2, 3, 4].map(i => <div key={i}/>)}</div></> : <p className="secondary">Trace data is unavailable. Retry the read above.</p>}</div>
              : !result.items.length && <div className="empty-state">
                <span className="empty-symbol"><Icon name={result.projectTotal === 0 ? 'runs' : 'search'}/></span>
                <h2>{result.projectTotal === 0 ? 'No traces yet' : 'No matching traces'}</h2>
                <p>{result.projectTotal === 0 ? live ? 'Run an agent with the SDK and its trace appears here. Home shows the commands.' : 'No captured executions are available for this project.' : 'No traces match these filters. Adjust or clear them.'}</p>
                {result.projectTotal === 0 && live && <a className="button" href={homeHref(project.id)}>Set up tracing<Icon name="arrow"/></a>}
                {result.projectTotal > 0 && <button className="button" onClick={() => replaceQuery(project.id, '')}>Reset query</button>}
              </div>}
          </RunTable>
          <footer className="table-footer"><span>{result ? `${result.total} trace${result.total === 1 ? '' : 's'}${busy ? ' · Refreshing data' : ''}` : live ? 'Backend telemetry repository' : 'Trace data source'}</span><div className="pagination"><label htmlFor="page-size">Rows per page</label><select id="page-size" aria-label="Rows per page" value={query.pageSize} onChange={event => change({ pageSize: Number(event.target.value) })}>{[5, 10, 25, 50].map(size => <option key={size}>{size}</option>)}</select><span>{result ? `Page ${result.page} of ${totalPages}` : 'Page —'}</span><button className="button small" aria-label="Previous page" aria-disabled={!canPrevious} onClick={() => { if (canPrevious) change({ page: result.page - 1 }) }}>Previous</button><button className="button small" aria-label="Next page" aria-disabled={!canNext} onClick={() => { if (canNext) change({ page: result.page + 1 }) }}>Next</button></div></footer>
        </div>
        {peek && traceRepository && <TracePeek repository={traceRepository} projectId={project.id} runId={peek} listSearch={key} position={{ index: peekIndex, total: items.length }} previous={previous} next={next} close={closePeek} width={peekWidth} minWidth={PEEK_MIN} maxWidth={peekMax} resize={value => setPeekWidth(String(Math.max(PEEK_MIN, Math.min(peekMax, Math.round(value)))))} resetWidth={() => setPeekWidth('auto')}/>}
      </div>
    </section>
  </AppShell>
}
