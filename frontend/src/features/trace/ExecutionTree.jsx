import { useLayoutEffect, useMemo } from 'react'
import Icon from '../../components/Icon.jsx'
import { useElementSize } from './useElementSize.js'
import { ROW_HEIGHT, windowRows, restoreAnchor, statusText, durationText, typeLabel, types, childLabel } from './treeModel.js'
import TimelineTrack from './TimelineTrack.jsx'
import { intervalLabel, timeLabel } from './timelineModel.js'

export default function ExecutionTree({ index, rows, ui, treeRef, select, patch, toggle, filtered, showIds, timing, timeWindow }) {
  const timeline = ui.view === 'timeline'
  const size = useElementSize(treeRef)
  const active = rows.some(row => row.id === ui.active && row.span) ? ui.active : rows.find(row => row.span)?.id
  const max = Math.max(0, rows.length * ROW_HEIGHT - size.height)
  const top = Math.min(max, ui.anchor ? restoreAnchor(rows, ui.anchor, index) : ui.scrollTop)
  const rendered = useMemo(() => windowRows(rows, top, size.height, active), [rows, top, size.height, active])
  useLayoutEffect(() => { if (treeRef.current && Math.abs(treeRef.current.scrollTop - top) > 0.5) treeRef.current.scrollTop = top }, [treeRef, top])
  function move(id) {
    const position = rows.findIndex(row => row.id === id)
    if (position < 0) return
    const rowTop = position * ROW_HEIGHT
    const next = rowTop < top ? rowTop : rowTop + ROW_HEIGHT > top + size.height ? rowTop + ROW_HEIGHT - size.height : top
    const anchorRow = rows[Math.floor(next / ROW_HEIGHT)]
    patch({ active: id, scrollTop: next, anchor: anchorRow ? { id: anchorRow.id, offset: next % ROW_HEIGHT } : null })
  }
  function keyboard(event) {
    const position = rows.findIndex(row => row.id === active)
    const row = rows[position]
    const dataRows = rows.filter(item => item.span)
    const n = dataRows.findIndex(item => item.id === active)
    let target
    if (event.key === 'ArrowDown') target = dataRows[n + 1]
    if (event.key === 'ArrowUp') target = dataRows[n - 1]
    if (event.key === 'Home') target = dataRows[0]
    if (event.key === 'End') target = dataRows.at(-1)
    if (event.key === 'PageDown') target = dataRows[Math.min(dataRows.length - 1, n + Math.max(1, Math.floor(size.height / ROW_HEIGHT)))]
    if (event.key === 'PageUp') target = dataRows[Math.max(0, n - Math.max(1, Math.floor(size.height / ROW_HEIGHT)))]
    if (event.key === 'ArrowRight' && row?.hasChildren) {
      if (!row.expanded && !filtered) toggle(row.id)
      else target = rows[position + 1]?.span ? rows[position + 1] : null
    }
    if (event.key === 'ArrowLeft' && row?.span) {
      if (row.expanded && row.hasChildren && !filtered) toggle(row.id)
      else { const parent = index.byId.get(row.span.parentId); if (parent) move(parent.id) }
    }
    if ((event.key === 'Enter' || event.key === ' ') && active) select(active)
    if (['ArrowDown', 'ArrowUp', 'Home', 'End', 'PageDown', 'PageUp', 'ArrowLeft', 'ArrowRight', 'Enter', ' '].includes(event.key)) event.preventDefault()
    if (target) move(target.id)
  }
  return <div className="trace-tree" role="tree" aria-label="Execution spans" aria-activedescendant={active ? `trace-row-${active}` : undefined} tabIndex="0" ref={treeRef} onKeyDown={keyboard} onScroll={event => {
    const scrollTop = event.currentTarget.scrollTop
    const row = rows[Math.floor(scrollTop / ROW_HEIGHT)]
    patch({ scrollTop, anchor: row ? { id: row.id, offset: scrollTop % ROW_HEIGHT } : null })
  }}>
    <div className="trace-canvas" style={{ height: Math.max(rows.length * ROW_HEIGHT, 1) }}>
      {rendered.map(row => row.group ? <div className="trace-group-row" key={row.id} style={{ top: row.index * ROW_HEIGHT }}><Icon name="error"/>{row.name}<span>UI grouping · not an operation</span></div> : <div key={row.id} id={`trace-row-${row.id}`} role="treeitem" data-span-id={row.id} className={`trace-row trace-grid${ui.selected === row.id ? ' selected' : ''}${active === row.id ? ' keyboard-active' : ''}`} style={{ top: row.index * ROW_HEIGHT }} aria-level={row.depth + 1} aria-posinset={row.position} aria-setsize={row.siblings} aria-selected={ui.selected === row.id} aria-expanded={row.hasChildren ? row.expanded : undefined} aria-label={`${row.span.name} · ${typeLabel(row.span.type)} · ${statusText(row.span.status)} · ${durationText(row.span.duration)} · ${row.id}${row.context ? ' · Ancestor context' : ''}`} aria-description={(timeline ? intervalLabel(timing.byId.get(row.id)) + '; ' : '') + `${row.childLoaded} loaded children; ${row.childKnown === null ? 'total unknown' : `${row.childKnown} known children`}`} title={`${row.span.name}\nSpan ${row.id}\nRecorded parent ${row.span.parentId ?? 'root'}\nDepth ${row.depth + 1}`} onClick={() => { treeRef.current.focus({ preventScroll: true }); select(row.id) }}>
        <div className="trace-operation" style={{ paddingLeft: Math.min(row.depth, timeline ? 3 : 6) * 16 }}>
          {row.hasChildren ? <button className={`tree-disclosure ${row.expanded ? 'expanded' : ''}`} data-disclosure="true" tabIndex="-1" aria-label={`${row.expanded ? 'Collapse' : 'Expand'} ${row.span.name}`} aria-disabled={filtered} title={filtered ? 'Matching ancestor paths stay visible while filtering' : undefined} onClick={event => { event.stopPropagation(); if (!filtered) toggle(row.id) }}><Icon name="chevron"/></button> : <span className="tree-disclosure"/>}
          <Icon name={types.includes(row.span.type) ? row.span.type : 'custom'}/>
          {row.depth > (timeline ? 3 : 6) && <span className="depth-marker" title={`Recorded depth ${row.depth + 1}`}>↳{row.depth + 1}</span>}
          <span className="trace-name-stack"><span className="trace-operation-name">{row.span.name}</span><span className="trace-inline-type">{typeLabel(row.span.type)} · {timeline ? <span className={row.span.status === 'ERROR' ? 'error-text' : ''}>{statusText(row.span.status)}</span> : `${Number.isFinite(row.span.start) && row.span.start >= 0 ? '+' : ''}${timeLabel(row.span.start)}`}{timeline && (row.childKnown === null || row.childKnown > 0 || row.childLoaded > 0) ? ` · ${childLabel(row)}` : ''}{row.context ? ' · ancestor' : ''}</span></span>
          {!timeline && (row.childKnown === null || row.childKnown > 0 || row.childLoaded > 0) && <span className="trace-child-count" title={`${row.childLoaded} loaded children; ${row.childKnown === null ? 'total unknown' : `${row.childKnown} known`}`}>{childLabel(row)}</span>}
          {row.span.retryOf && <span className="trace-retry-glyph" title={`Recorded retry of ${row.span.retryOf}`}><Icon name="retry"/></span>}
        </div>
        {timeline ? <><TimelineTrack timing={timing.byId.get(row.id)} window={timeWindow} status={row.span.status}/><span className="sr-only">{timing.byId.get(row.id)?.state === 'valid' ? `Recorded interval ${timeLabel(timing.byId.get(row.id).start)} to ${timeLabel(timing.byId.get(row.id).end)}` : timing.byId.get(row.id)?.reason}</span></> : <>
          {showIds && <span className="trace-id-cell mono" title={row.id}>{row.id}</span>}
          <span className="trace-start-cell mono" title="Recorded offset from run start">{Number.isFinite(row.span.start) && row.span.start >= 0 ? '+' : ''}{timeLabel(row.span.start)}</span>
          <span className="trace-type-cell">{typeLabel(row.span.type)}</span>
          <span className={`trace-status-cell ${row.span.status === 'ERROR' ? 'error-text' : ''}`} title={statusText(row.span.status)}>{statusText(row.span.status)}</span>
        </>}
        <span className="trace-duration mono">{durationText(row.span.duration)}</span>
      </div>)}
    </div>
    {!rows.length && <div className="empty-state"><h3>No matching loaded spans</h3><p>Change the loaded-only search or filters.</p></div>}
  </div>
}
