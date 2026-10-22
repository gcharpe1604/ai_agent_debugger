import { it, expect, vi } from 'vitest'
import { readPreference, writePreference } from './preferences.js'

it('persists only the requested presentation value', () => {
  writePreference('theme', 'dark')
  expect(localStorage.getItem('agent-debugger.frontend.v1.theme')).toBe('dark')
  expect(readPreference('theme', ['light', 'dark', 'system'], 'system')).toBe('dark')
})
it('rejects stale preference values rather than applying an unknown theme', () => {
  localStorage.setItem('agent-debugger.frontend.v1.theme', 'neon')
  expect(readPreference('theme', ['light', 'dark', 'system'], 'system')).toBe('system')
})
it('keeps the app usable when storage is blocked', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('Storage blocked') })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Storage blocked') })
  expect(readPreference('theme', ['light', 'dark', 'system'], 'system')).toBe('system')
  expect(() => writePreference('theme', 'dark')).not.toThrow()
})
