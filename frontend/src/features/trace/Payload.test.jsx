import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Payload from './Payload.jsx'
import { initialTraceState, returnQuery } from './traceState.js'

describe('Captured values and navigation identity', () => {
  it.each([null, false, 0, '', []])('does not replace the captured value %j with an unavailable state', value => {
    render(<Payload label="Input" value={value} capture={{ state: 'captured' }} format="JSON" wrap/>)
    expect(screen.getByText('Captured')).toBeTruthy()
    expect(document.querySelector('pre').textContent).toBe(JSON.stringify(value, null, 2))
  })
  it.each(['unavailable', 'disabled', 'unsupported', 'error'])('hides absent %s payloads and preserves the capture reason', state => {
    render(<Payload label="Output" value="MUST_NOT_RENDER" capture={{ state, reason: 'Capture policy explanation' }} format="Readable"/>)
    expect(screen.getByText('Capture policy explanation')).toBeTruthy()
    expect(screen.queryByText('MUST_NOT_RENDER')).toBeNull()
  })
  it('preserves closed selection on reload while stripping only trace query from the Runs return link', () => {
    const query = 'search=order&outcome=Completed&span=abc&spanStatus=ERROR&loaded=1260&panel=closed'
    expect(initialTraceState(query, null, 'pinned')).toMatchObject({ selected: 'abc', open: false, mode: 'pinned', status: 'ERROR' })
    expect(returnQuery(query)).toBe('search=order&outcome=Completed')
  })
})
