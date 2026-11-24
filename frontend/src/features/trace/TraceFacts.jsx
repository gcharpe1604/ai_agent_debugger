import Icon from '../../components/Icon.jsx'
import Timestamp from '../../components/Timestamp.jsx'
import Tooltip from '../../components/ui/Tooltip.jsx'
import { Popover, PopoverContent, PopoverTrigger } from '../../components/ui/Popover.jsx'
import { exactDuration } from '../../app/format.js'
import { durationText, typeLabel } from './treeModel.js'
import { TRACE_FACTS } from './traceStats.js'

// Trace header line 2: Started · Duration · Spans · Errors · Depth, then a
// Types popover. `spansNote` (for example "received; completeness unknown") is
// only in the Spans tooltip.
export default function TraceFacts({ run, stats, spansNote }) {
  const plural = (count, word) => `${count.toLocaleString('en')} ${word}${count === 1 ? '' : 's'}`
  const items = {
    started: <li key="started" data-stat="started" className="trace-stat" title="Started"><Icon name="calendar"/><span className="sr-only">Started </span><Timestamp value={run.startedAt}/></li>,
    duration: <li key="duration" data-stat="duration" className="trace-stat" title={`Duration · ${exactDuration(run.durationMs)}`}><Icon name="timer"/><span className="sr-only">Duration </span><span className="tabular">{durationText(run.durationMs)}</span></li>,
    spans: <Tooltip key="spans" content={spansNote}><li data-stat="spans" className="trace-stat" tabIndex={spansNote ? 0 : undefined}><Icon name="layers"/><span className="tabular">{plural(stats.spans, 'span')}</span></li></Tooltip>,
    errors: <li key="errors" data-stat="errors" className="trace-stat" data-tone={stats.errors > 0 ? 'error' : undefined}><Icon name="error"/><span className="tabular">{plural(stats.errors, 'error')}</span></li>,
    depth: <li key="depth" data-stat="depth" className="trace-stat" title="Deepest parent chain"><Icon name="depth"/><span className="tabular">Depth {stats.depth}</span></li>,
  }
  return <div className="trace-facts">
    <ul className="trace-stats" aria-label="Trace facts">{TRACE_FACTS.map(key => items[key])}</ul>
    {stats.byType.length > 0 && <Popover>
      <PopoverTrigger><button type="button" className="button ghost small trace-types-button"><Icon name="shapes"/>Types</button></PopoverTrigger>
      <PopoverContent className="trace-popover trace-types" align="start">
        <ul aria-label="Spans by type">{stats.byType.map(([type, count]) => <li key={type} data-type={type}><Icon name={type}/><span>{typeLabel(type)}</span><span className="tabular">{count.toLocaleString('en')}</span></li>)}</ul>
      </PopoverContent>
    </Popover>}
  </div>
}
