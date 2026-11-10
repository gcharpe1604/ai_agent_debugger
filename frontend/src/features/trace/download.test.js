import { describe, expect, it, vi } from 'vitest'
import { downloadTrace, traceDocument } from './download.js'

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
})
