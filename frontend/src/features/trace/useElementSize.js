import { useLayoutEffect, useState } from 'react'

export function useElementSize(ref, fallback = { width: 1208, height: 600 }) {
  const [size, setSize] = useState(fallback)
  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    function measure() {
      const rect = element.getBoundingClientRect()
      const gutter = Math.round(rect.width - element.clientWidth)
      if (rect.width && rect.height) setSize(old => old.width === rect.width && old.height === rect.height && old.gutter === gutter ? old : { width: rect.width, height: rect.height, gutter })
    }
    measure()
    if (typeof ResizeObserver !== 'undefined') { const observer = new ResizeObserver(measure); observer.observe(element); return () => observer.disconnect() }
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [ref])
  return size
}
