import { useMemo } from 'react'
import Icon from '../components/Icon.jsx'
import RunTable from '../features/runs/RunTable.jsx'
import RunToolbar from '../features/runs/RunToolbar.jsx'
import { useRuns } from '../features/runs/useRuns.js'
import { changeQuery, parseQuery, queryString } from '../features/runs/query.js'
import { replaceQuery } from '../app/routes.jsx'

export default function RunExplorerPage({ project, search, repository }) {
  const query = useMemo(() => parseQuery(search), [search])
  const key = queryString(query)
  const { result, error, busy, refresh } = useRuns(repository, project.id, query, key)
  const change = patch => replaceQuery(project.id, queryString(changeQuery(query, patch)))
  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.pageSize)) : 1
  const canPrevious = !busy && result && result.page > 1
  const canNext = !busy && result && result.page < totalPages
  return <section className="explorer" aria-labelledby="runs-heading"><div className="view-heading"><h1 id="runs-heading">Runs{result && <span className="count">{result.total}</span>}</h1><button className="button" onClick={refresh} disabled={busy}><Icon name="refresh"/>{busy && result ? 'Refreshing…' : 'Refresh'}</button></div>
    <RunToolbar query={query} onChange={change} onReset={() => replaceQuery(project.id, '')}/>
    {error && <div className="read-error" role="alert"><Icon name="error"/><div><strong>Could not load runs</strong><p>{error}{result ? ' Previously loaded sample data is shown.' : ''}</p></div><button className="button" onClick={refresh}>Retry</button></div>}
    <div className="sr-only" role="status" aria-live="polite">{busy ? result ? 'Refreshing sample runs' : 'Loading sample runs' : error ? 'Run read failed' : `${result?.total || 0} sample runs. Page ${result?.page || 1} of ${totalPages}.`}</div>
    <RunTable items={result?.items || []} projectId={project.id} search={key} query={query} onSort={sort => change({ sort, direction: query.sort === sort && query.direction === 'asc' ? 'desc' : 'asc' })} busy={busy}>
      {!result ? <div className="state-region">{busy ? <><span className="secondary">Loading runs…</span><div className="loading-rows" aria-hidden="true">{[0, 1, 2, 3, 4].map(i => <div key={i}/>)}</div></> : <p className="secondary">Run data is unavailable. Retry the read above.</p>}</div>
        : !result.items.length && <div className="empty-state"><h2>{result.projectTotal === 0 ? 'No runs recorded' : 'No matching runs'}</h2><p>{result.projectTotal === 0 ? 'This sample project has no runs. SDK onboarding is outside Milestone 1.' : 'No sample runs match this query. Adjust the filters or widen the sample time window.'}</p>{result.projectTotal > 0 && <button className="button" onClick={() => replaceQuery(project.id, '')}>Reset query</button>}</div>}
    </RunTable>
    <footer className="table-footer"><span>{result ? `${result.total} run${result.total === 1 ? '' : 's'}${busy ? ' · Refreshing sample data' : ''}` : 'Sample run repository'}</span><div className="pagination"><label htmlFor="page-size">Rows per page</label><select id="page-size" aria-label="Rows per page" value={query.pageSize} onChange={event => change({ pageSize: Number(event.target.value) })}>{[5, 10, 25, 50].map(size => <option key={size}>{size}</option>)}</select><span>{result ? `Page ${result.page} of ${totalPages}` : 'Page —'}</span><button className="button small" aria-label="Previous page" aria-disabled={!canPrevious} onClick={() => { if (canPrevious) change({ page: result.page - 1 }) }}>Previous</button><button className="button small" aria-label="Next page" aria-disabled={!canNext} onClick={() => { if (canNext) change({ page: result.page + 1 }) }}>Next</button></div></footer>
  </section>
}
