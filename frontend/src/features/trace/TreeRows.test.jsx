import { beforeEach, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from '../../test/FixtureApp.jsx'
import { traceRepository } from '../../data/traceRepository.js'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Vitest runs from the frontend folder.
const traceCss = readFileSync(resolve('src/features/trace/trace.css'), 'utf8')

// Vitest does not load CSS and jsdom cannot parse this stylesheet (container
// queries, color-mix), so the top-level rules are read here and matched
// against the rendered rows.
function topLevelRules(css) {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, '')
  const rules = []
  let depth = 0, start = 0, selector = ''
  for (let i = 0; i < text.length; i++) {
    if (text[i] === '{') { if (depth === 0) { selector = text.slice(start, i).trim(); start = i + 1 } depth++ }
    else if (text[i] === '}') { depth--; if (depth === 0) { if (!selector.startsWith('@')) rules.push({ selector, body: text.slice(start, i) }); start = i + 1 } }
  }
  return rules
}

beforeEach(() => window.history.replaceState(null, '', '/#/projects/agent-examples/runs/R-1040'))

it('renders tree rows without border lines, with connector guides from the model', async () => {
  render(<App traceRepository={traceRepository}/>)
  const rows = await screen.findAllByRole('treeitem')
  const matching = topLevelRules(traceCss).filter(rule => rows.some(row => { try { return row.matches(rule.selector) } catch { return false } }))
  expect(matching.map(rule => rule.selector)).toContain('.trace-row')
  // No rule that applies to a row draws a border line or a box-shadow line;
  // only the left accent bar (border-left) of the selected row remains.
  const lines = matching.filter(rule => /(^|;)\s*(box-shadow|border|border-top|border-bottom)\s*:/.test(rule.body)).map(rule => rule.selector)
  expect(lines).toEqual([])
  // The root has no guide; every other visible row has exactly one elbow.
  expect(rows[0].querySelector('.tree-elbow')).toBeNull()
  expect(rows.slice(1).every(row => row.querySelectorAll('.tree-elbow').length === 1)).toBe(true)
})
