import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

Object.defineProperty(window, 'matchMedia', { writable: true, value: vi.fn(() => ({ matches: false, addEventListener() {}, removeEventListener() {} })) })
afterEach(() => { cleanup(); localStorage.clear(); window.history.replaceState(null, '', '/'); document.documentElement.removeAttribute('data-theme') })
