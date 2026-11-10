import { describe, it, expect } from 'vitest'
import { executionModeLabel, firstErrorText, firstErrorTitle, formatCost, ioPreview, runColumns } from './runColumns.js'

const run = (completeness, investigation) => ({ completeness, investigation })
const fields = items => runColumns(items).map(([field]) => field)

describe('run column hiding', () => {
  it('hides Completeness and Investigation while every visible row is Unknown/Unavailable', () => {
    expect(fields([run('Unknown', 'Unavailable'), run('Unknown', 'Unavailable')])).toEqual(['name', 'outcome', 'startedAt', 'durationMs', 'recordedErrorCount'])
  })
  it('brings each column back as soon as one row has a real value', () => {
    expect(fields([run('Unknown', 'Unavailable'), run('Partial', 'Unavailable')])).toContain('completeness')
    expect(fields([run('Unknown', 'Unavailable'), run('Partial', 'Unavailable')])).not.toContain('investigation')
    expect(fields([run('Unknown', 'Completed')])).toEqual(['name', 'outcome', 'startedAt', 'durationMs', 'recordedErrorCount', 'investigation'])
  })
  it('shows model usage columns only once a visible trace records them', () => {
    expect(fields([run('Unknown', 'Unavailable')])).not.toContain('totalTokens')
    expect(fields([run('Unknown', 'Unavailable'), { ...run('Unknown', 'Unavailable'), model: 'gpt-x', totalTokens: 812, costUsd: 0.0021 }])).toEqual(['name', 'outcome', 'startedAt', 'durationMs', 'model', 'totalTokens', 'costUsd', 'recordedErrorCount'])
    expect([formatCost(0.0021), formatCost(1.5), formatCost(null)]).toEqual(['$0.0021', '$1.50', '—'])
  })
  it('previews input → output on one clipped line, only when supplied', () => {
    expect(ioPreview({})).toBeNull()
    expect(ioPreview({ inputPreview: 'LG-01', outputPreview: null })).toBe('LG-01 → —')
    expect(ioPreview({ inputPreview: 'x'.repeat(100), outputPreview: 'ok' }, 10)).toBe(`${'x'.repeat(9)}… → ok`)
  })
  it('labels the error column "Error spans"', () => {
    expect(runColumns([run('Complete', 'Completed')]).find(([field]) => field === 'recordedErrorCount')[1]).toBe('Error spans')
  })
})

describe('first error and mode labels', () => {
  it('formats exception · span name with the count of the other deepest error spans', () => {
    const pay = { exceptionType: 'ToolTimeout', spanName: 'LocalTools.invoke · pay · attempt 1', operationType: 'tool', spanId: 'a000000000000002', leafErrorCount: 3 }
    expect(firstErrorText(pay)).toBe('ToolTimeout · LocalTools.invoke · pay · attempt 1 (+2)')
    expect(firstErrorTitle(pay)).toMatch(/Tool span a000000000000002\. .*not a cause\.$/)
    expect(firstErrorText({ exceptionType: null, spanName: 'retrieve', operationType: 'retrieval', leafErrorCount: 1 })).toBe('retrieve')
    expect(firstErrorText(null)).toBeNull()
  })
  it('shows Controlled/Live and nothing for null', () => {
    expect([executionModeLabel('controlled'), executionModeLabel('live'), executionModeLabel(null)]).toEqual(['Controlled', 'Live', null])
  })
})
