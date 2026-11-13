import { describe, expect, it, vi } from 'vitest'
import { downloadTrace, downloadTraceList, traceDocument, traceListDocument } from './download.js'

const data = { run: { traceId: 'ab'.repeat(16), name: 'agent' }, spans: [{ id: 's1', parentId: null, name: 'agent' }] }

describe('trace download', () => {
  it('wraps exactly the received run and spans', () => {
    expect(traceDocument(data, '2026-11-11T00:00:00.000Z')).toEqual({ format: 'agent-debugger.trace.v1', exported_at: '2026-11-11T00:00:00.000Z', trace_id: data.run.traceId, run: data.run, spans: data.spans })
  })
  it('saves trace-<id>.json and releases the object URL', () => {
    const url = { createObjectURL: vi.fn(() => 'blob:trace'), revokeObjectURL: vi.fn() }
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () { expect(this.download).toBe(`trace-${data.run.traceId}.json`) })
    downloadTrace(data, { document, url })
    expect(click).toHaveBeenCalledTimes(1)
    expect(url.revokeObjectURL).toHaveBeenCalledWith('blob:trace')
    expect(document.querySelector('a[download]')).toBeNull()
    click.mockRestore()
  })
  it('exports the current list page as summaries with its query', () => {
    const result = { items: [data.run], total: 12, page: 2, pageSize: 5 }
    const query = { search: 'agent', page: 2, pageSize: 5 }
    expect(traceListDocument({ projectId: 'local', query, result }, '2026-11-11T00:00:00.000Z')).toEqual({ format: 'agent-debugger.trace-list.v1', exported_at: '2026-11-11T00:00:00.000Z', project_id: 'local', query, total_matching: 12, page: 2, page_size: 5, traces: [data.run] })
    const url = { createObjectURL: vi.fn(() => 'blob:list'), revokeObjectURL: vi.fn() }
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () { expect(this.download).toBe('traces-local-page-2.json') })
    downloadTraceList({ projectId: 'local', query, result }, { document, url })
    expect(click).toHaveBeenCalledTimes(1)
    expect(url.revokeObjectURL).toHaveBeenCalledWith('blob:list')
    click.mockRestore()
  })
})
