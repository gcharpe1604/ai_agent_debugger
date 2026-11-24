import { beforeEach, afterEach, vi } from 'vitest'
import { cleanup, configure } from '@testing-library/react'
import { clearSessionValues } from '../app/sessionMemory.js'

// findBy* waits up to 3 s: the full parallel run is several times slower than one file.
configure({ asyncUtilTimeout: 3000 })

// jsdom lacks the pointer-capture and scrolling APIs Radix menus and selects call.
Element.prototype.hasPointerCapture ??= () => false
Element.prototype.setPointerCapture ??= () => {}
Element.prototype.releasePointerCapture ??= () => {}
Element.prototype.scrollIntoView ??= () => {}
Object.defineProperty(window, 'matchMedia', { writable: true, value: vi.fn(() => ({ matches: false, addEventListener() {}, removeEventListener() {} })) })
// Fixture suites opt into their historical project URL only in the test environment.
beforeEach(() => window.history.replaceState(null, '', '/#/projects/agent-examples/runs'))
afterEach(() => { cleanup(); clearSessionValues(); localStorage.clear(); window.history.replaceState(null, '', '/'); document.documentElement.removeAttribute('data-theme') })
