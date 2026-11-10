import { useMemo } from 'react'
import Icon from '../components/Icon.jsx'
import UpdatedAgo from '../components/UpdatedAgo.jsx'
import RunTable from '../features/runs/RunTable.jsx'
import RunToolbar from '../features/runs/RunToolbar.jsx'
import FacetSidebar from '../features/runs/FacetSidebar.jsx'
import { useRuns } from '../features/runs/useRuns.js'
import { changeQuery, parseQuery, queryString } from '../features/runs/query.js'
import { replaceQuery, setupHref } from '../app/routes.jsx'
import { usePreference } from '../app/preferences.js'

const narrowScreen = () => typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 767px)').matches

function RunSummary({ result, busy }) {
  const items = [
    { label: 'Matching traces', value: result?.total, icon: 'runs' },
    { label: 'Failed traces', value: result?.summary?.failed, icon: 'error', tone: 'failure' },
    { label: 'Traces with error spans', value: result?.summary?.withSpanErrors, icon: 'branch' },
  ]
  return <dl className="run-summary" aria-label="Current results" aria-busy={busy}>
    {items.map(({ label, value, icon, tone }) => <div key={label} className="run-metric" data-tone={tone}>
      <dt>{label}<span className="run-metric-icon" aria-hidden="true"><Icon name={icon}/></span></dt>
      <dd>{value?.toLocaleString('en') ?? '—'}</dd>
    </div>)}
  </dl>
}

export default function RunExplorerPage({ project, search, repository }) {
  const live = project.dataSource === 'local'
  // Open by default on wide screens; on phones the table comes first. A saved choice wins.
  const [filters, setFilters] = usePreference('traces.filters', ['open', 'closed'], narrowScreen() ? 'closed' : 'open')
  const query = useMemo(() => ({ ...parseQuery(search), ...(live ? { time: 'all' } : {}) }), [search, live])
  const key = queryString(query)
  const { result, loadedAt, error, busy, refresh } = useRuns(repository, project.id, query, key)
  const change = patch => replaceQuery(project.id, queryString(changeQuery(query, patch)))
  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.pageSize)) : 1
  const canPrevious = !busy && result && result.page > 1
  const canNext = !busy && result && result.page < totalPages
  const showFilters = live && filters === 'open'
  return <section className="explorer" data-source={live ? 'local' : undefined} aria-labelledby="runs-heading">
    <div className="view-heading">
      <div><h1 id="runs-heading">Traces</h1><p className="view-description">Each trace is one agent run. Open one to inspect its spans.</p></div>
      <div className="view-actions">
        {!busy && <UpdatedAgo at={loadedAt}/>}
        <button className="button" onClick={refresh} disabled={busy} title="Read the latest captured traces"><Icon name="refresh"/>{busy && result ? 'Refreshing…' : 'Refresh'}</button>
      </div>
    </div>
    {live && (busy || result?.summary) && <RunSummary result={result} busy={busy}/>}
    <div className={`traces-layout${showFilters ? ' with-filters' : ''}`}>
      {showFilters && <div id="trace-filters"><FacetSidebar query={query} facets={result?.facets} onChange={change} onClose={() => setFilters('closed')}/></div>}
      <div className="runs-ledger">
        <RunToolbar live={live} query={query} onChange={change} onReset={() => replaceQuery(project.id, '')} filtersOpen={showFilters} toggleFilters={() => setFilters(showFilters ? 'closed' : 'open')}/>
        {error && <div className="read-error" role="alert"><Icon name="error"/><div><strong>Could not load traces</strong><p>{error}{result ? ' Previously loaded data is shown.' : ''}</p></div><button className="button" onClick={refresh}>Retry</button></div>}
        <div className="sr-only" role="status" aria-live="polite">{busy ? result ? 'Refreshing traces' : 'Loading traces' : error ? 'Trace read failed' : `${result?.total || 0} captured traces. Page ${result?.page || 1} of ${totalPages}.`}</div>
        <RunTable live={live} items={result?.items || []} projectId={project.id} search={key} query={query} onSort={sort => change({ sort, direction: query.sort === sort && query.direction === 'asc' ? 'desc' : 'asc' })} busy={busy}>
          {!result ? <div className="state-region">{busy ? <><span className="secondary">Loading traces…</span><div className="loading-rows" aria-hidden="true">{[0, 1, 2, 3, 4].map(i => <div key={i}/>)}</div></> : <p className="secondary">Trace data is unavailable. Retry the read above.</p>}</div>
            : !result.items.length && <div className="empty-state">
              <span className="empty-symbol"><Icon name={result.projectTotal === 0 ? 'runs' : 'search'}/></span>
              <h2>{result.projectTotal === 0 ? 'No traces yet' : 'No matching traces'}</h2>
              <p>{result.projectTotal === 0 ? live ? 'Run an agent with the SDK and its trace appears here. Get started walks you through it.' : 'No captured executions are available for this project.' : 'No traces match these filters. Adjust or clear them.'}</p>
              {result.projectTotal === 0 && live && <a className="button" href={setupHref(project.id)}>Get started<Icon name="arrow"/></a>}
              {result.projectTotal > 0 && <button className="button" onClick={() => replaceQuery(project.id, '')}>Reset query</button>}
            </div>}
        </RunTable>
        <footer className="table-footer"><span>{result ? `${result.total} trace${result.total === 1 ? '' : 's'}${busy ? ' · Refreshing data' : ''}` : live ? 'Backend telemetry repository' : 'Trace data source'}</span><div className="pagination"><label htmlFor="page-size">Rows per page</label><select id="page-size" aria-label="Rows per page" value={query.pageSize} onChange={event => change({ pageSize: Number(event.target.value) })}>{[5, 10, 25, 50].map(size => <option key={size}>{size}</option>)}</select><span>{result ? `Page ${result.page} of ${totalPages}` : 'Page —'}</span><button className="button small" aria-label="Previous page" aria-disabled={!canPrevious} onClick={() => { if (canPrevious) change({ page: result.page - 1 }) }}>Previous</button><button className="button small" aria-label="Next page" aria-disabled={!canNext} onClick={() => { if (canNext) change({ page: result.page + 1 }) }}>Next</button></div></footer>
      </div>
    </div>
  </section>
}
