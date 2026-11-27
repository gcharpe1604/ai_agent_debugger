// Syntax-highlighting themes for Expressive Code, built from the app's design
// tokens (frontend/src/styles/tokens.css) at config time, so code blocks use the
// same colours as the landing page: keywords --type-agent, strings --json-string,
// comments --color-muted (docs/frontend/landing-spec.md §4).
// Expressive Code needs concrete colours for its themes, so the token values are
// read from the file here rather than copied.
import { readFileSync } from 'node:fs'

const TOKENS = new URL('../../frontend/src/styles/tokens.css', import.meta.url)

function block(css, selector) {
  const start = css.indexOf(selector)
  if (start < 0) throw new Error(`tokens.css: no ${selector} block`)
  const open = css.indexOf('{', start)
  return css.slice(open + 1, css.indexOf('}', open))
}

function variables(body) {
  const out = {}
  for (const [, name, value] of body.matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)) out[name] = value.trim()
  return out
}

// "#rrggbb", "#rgb" or "hsl(h s% l%)" → "#rrggbb".
function hex(value) {
  if (/^#[0-9a-f]{6}$/i.test(value)) return value.toLowerCase()
  if (/^#[0-9a-f]{3}$/i.test(value)) return '#' + [...value.slice(1)].map(c => c + c).join('').toLowerCase()
  const match = /^hsl\(\s*([\d.]+)\s+([\d.]+)%\s+([\d.]+)%\s*\)$/.exec(value)
  if (!match) throw new Error(`tokens.css: unsupported colour ${value}`)
  const [h, s, l] = [Number(match[1]), Number(match[2]) / 100, Number(match[3]) / 100]
  const a = s * Math.min(l, 1 - l)
  const channel = n => {
    const k = (n + h / 30) % 12
    return Math.round(255 * (l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1)))).toString(16).padStart(2, '0')
  }
  return `#${channel(0)}${channel(8)}${channel(4)}`
}

function theme(name, type, t) {
  return {
    name,
    type,
    colors: { 'editor.background': hex(t['color-sidebar']), 'editor.foreground': hex(t['color-text']) },
    tokenColors: [
      { scope: ['comment', 'punctuation.definition.comment'], settings: { foreground: hex(t['color-muted']) } },
      { scope: ['string', 'punctuation.definition.string', 'string.unquoted.value'], settings: { foreground: hex(t['json-string']) } },
      {
        scope: ['keyword', 'storage', 'storage.type', 'storage.modifier', 'keyword.control', 'keyword.other', 'support.function.builtin'],
        settings: { foreground: hex(t['type-agent']) },
      },
      { scope: ['constant.numeric'], settings: { foreground: hex(t['json-number']) } },
      { scope: ['constant.language'], settings: { foreground: hex(t['json-boolean']) } },
      { scope: ['punctuation', 'keyword.operator'], settings: { foreground: hex(t['color-text-secondary']) } },
    ],
  }
}

export function tokenThemes() {
  const css = readFileSync(TOKENS, 'utf8')
  const light = variables(block(css, ':root'))
  const dark = { ...light, ...variables(block(css, '[data-theme="dark"]')) }
  return [theme('agent-debugger-dark', 'dark', dark), theme('agent-debugger-light', 'light', light)]
}
