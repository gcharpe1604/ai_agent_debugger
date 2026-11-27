// Vercel build for the one frontend project: the app, then the docs site,
// served from the same output directory.
//
//   frontend/dist/            the React app (vite build)
//   frontend/dist/docs/       the Astro Starlight docs (docs-site/dist/docs)
//   frontend/dist/404.html    the docs 404 page; Vercel serves it for a missing
//                             /docs/... path (the SPA fallback skips /docs)
//
// frontend/vercel.json runs it as `node ../scripts/build-vercel.mjs` from frontend/,
// after Vercel's own `npm install` there. Works the same from any directory:
//   node scripts/build-vercel.mjs
import { spawnSync } from 'node:child_process'
import { cpSync, existsSync, rmSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const repo = join(dirname(fileURLToPath(import.meta.url)), '..')
const frontend = join(repo, 'frontend')
const docsSite = join(repo, 'docs-site')
const appDist = join(frontend, 'dist')
const docsDist = join(docsSite, 'dist', 'docs')

function npm(cwd, ...args) {
  console.log(`\n> npm ${args.join(' ')}   (${cwd})`)
  // npm is npm.cmd on Windows, which Node only runs through a shell.
  const result = spawnSync('npm', args, { cwd, stdio: 'inherit', shell: process.platform === 'win32' })
  if (result.status !== 0) {
    console.error(`npm ${args.join(' ')} failed in ${cwd} (exit ${result.status ?? result.signal})`)
    process.exit(result.status || 1)
  }
}

npm(frontend, 'run', 'build')
npm(docsSite, 'ci', '--no-audit', '--no-fund')
npm(docsSite, 'run', 'build')

if (!existsSync(join(docsDist, 'index.html'))) {
  console.error(`No docs build at ${docsDist}`)
  process.exit(1)
}
rmSync(join(appDist, 'docs'), { recursive: true, force: true })
cpSync(docsDist, join(appDist, 'docs'), { recursive: true })
cpSync(join(docsDist, '404.html'), join(appDist, '404.html'))
console.log(`\nCopied ${docsDist} -> ${join(appDist, 'docs')} (and docs/404.html -> 404.html)`)
