// Every page of the docs site served at /docs/, as the path after /docs/.
// Source: docs-site/src/content/docs on branch feat/docs-site (index.mdx is '').
// `npm run build` runs scripts/check-docs-links.mjs, which fails when a docs link
// in src/ is not listed here, or (when docs-site/ is checked out next to frontend/)
// when a page listed here has no file.
export const DOCS_PAGES = [
  '',
  'get-started/quickstart/',
  'sdk/trace-session/',
  'sdk/opentelemetry/',
  'sdk/capture-and-redaction/',
  'concepts/runs-and-spans/',
  'concepts/errors-and-retries/',
  'concepts/payloads/',
  'product/dashboard/',
  'product/tracing/',
  'product/trace-view/',
  'product/settings/',
  'api/ingest/',
  'api/accounts/',
  'api/reading-runs/',
  'api/errors/',
  'self-hosting/docker-compose/',
  'self-hosting/configuration/',
  'self-hosting/upgrade-and-backup/',
  'limits/',
]
