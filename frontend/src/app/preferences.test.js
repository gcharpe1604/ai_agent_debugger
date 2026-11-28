import { it, expect, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { readPreference, useTheme, writePreference } from './preferences.js'

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
it('shares one theme between every useTheme caller and follows other tabs', () => {
  const first = renderHook(() => useTheme()), second = renderHook(() => useTheme())
  expect(first.result.current.preference).toBe('system')
  act(() => first.result.current.setPreference('dark'))
  expect(second.result.current.resolved).toBe('dark')
  expect(localStorage.getItem('agent-debugger.frontend.v1.theme')).toBe('dark')
  // The docs site (same origin, other tab) writes the same key.
  act(() => { localStorage.setItem('agent-debugger.frontend.v1.theme', 'light'); window.dispatchEvent(new StorageEvent('storage', { key: 'agent-debugger.frontend.v1.theme' })) })
  expect(first.result.current.resolved).toBe('light')
  expect(second.result.current.preference).toBe('light')
})
