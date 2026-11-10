import { describe, it, expect } from 'vitest'
import { executionModeLabel, firstErrorText, firstErrorTitle, runColumns } from './runColumns.js'

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
