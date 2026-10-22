import { beforeEach, afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

Object.defineProperty(window, 'matchMedia', { writable: true, value: vi.fn(() => ({ matches: false, addEventListener() {}, removeEventListener() {} })) })
// Fixture suites opt into their historical project URL only in the test environment.
beforeEach(() => window.history.replaceState(null, '', '/#/projects/agent-examples/runs'))
afterEach(() => { cleanup(); localStorage.clear(); window.history.replaceState(null, '', '/'); document.documentElement.removeAttribute('data-theme') })
