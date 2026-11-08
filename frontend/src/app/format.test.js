import { describe, it, expect } from 'vitest'
import { exactDuration, formatDuration } from './format.js'

describe('formatDuration boundaries', () => {
  it.each([
    [0, '0.00 ms'], [4.267, '4.27 ms'], [9.99, '9.99 ms'],
    [9.996, '10.0 ms'], [10, '10.0 ms'], [245.34, '245.3 ms'], [999.9, '999.9 ms'],
    [999.96, '1.00 s'], [1000, '1.00 s'], [12345, '12.35 s'], [59994, '59.99 s'],
    [59996, '1m 00s'], [60000, '1m 00s'], [65000, '1m 05s'], [3599000, '59m 59s'], [3600000, '60m 00s'],
  ])('%s ms → %s', (value, text) => expect(formatDuration(value)).toBe(text))

  it('keeps the sign for negative offsets and rejects non-finite input', () => {
    expect(formatDuration(-1500)).toBe('-1.50 s')
    expect(formatDuration(-2)).toBe('-2.00 ms')
    for (const value of [NaN, Infinity, null, undefined]) expect(formatDuration(value)).toBe('Unavailable')
  })

  it('exact values are never rounded', () => {
    expect(exactDuration(2418.004)).toBe('2418.004 ms')
    expect(exactDuration(null)).toBe('Unavailable')
  })
})
