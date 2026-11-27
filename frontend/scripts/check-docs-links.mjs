// Fails (exit 1) when a docs link in src/ has no page on the docs site.
// 1. Every docsUrl('…') call and every '/docs/…' string literal in src/ must name
//    a page in DOCS_PAGES (src/features/public/docsPages.js).
// 2. When ../docs-site/src/content/docs (or $DOCS_SITE_CONTENT) exists, every DOCS_PAGES entry must have a
//    source file there, so the list cannot go stale once the docs site is merged.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import { DOCS_PAGES } from '../src/features/public/docsPages.js'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const pages = new Set(DOCS_PAGES)
const problems = []

function sources(dir) {
  return readdirSync(dir).flatMap(name => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return sources(path)
    return /\.(jsx?|mjs)$/.test(name) && !/\.test\.jsx?$/.test(name) ? [path] : []
  })
}

let links = 0
for (const file of sources(join(root, 'src'))) {
  const text = readFileSync(file, 'utf8')
  const found = [
    ...[...text.matchAll(/docsUrl\(\s*(?:'([^']*)'|"([^"]*)")?\s*\)/g)].map(m => m[1] ?? m[2] ?? ''),
    ...[...text.matchAll(/['"`]\/docs\/([^'"`$]*)['"`]/g)].map(m => m[1]),
  ]
  for (const page of found) {
    links += 1
    if (!pages.has(page)) problems.push(`${relative(root, file)}: /docs/${page} is not a docs page`)
  }
}

const content = process.env.DOCS_SITE_CONTENT || join(root, '..', 'docs-site', 'src', 'content', 'docs')
const checkedFiles = existsSync(content)
if (checkedFiles) {
  for (const page of DOCS_PAGES) {
    const base = page === '' ? 'index' : page.replace(/\/$/, '')
    if (!['.md', '.mdx'].some(ext => existsSync(join(content, base + ext)))) problems.push(`docsPages.js: /docs/${page} has no file in docs-site/src/content/docs`)
  }
}

if (problems.length) {
  console.error(`Docs link check failed:\n  ${problems.join('\n  ')}`)
  process.exit(1)
}
console.log(`Docs link check: ${links} links, ${DOCS_PAGES.length} pages${checkedFiles ? ', all present in docs-site' : ' (docs-site/ not present; list not compared)'}`)
