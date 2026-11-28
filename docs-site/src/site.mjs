// Shared links for the docs chrome (header, mobile menu, footer). The app's
// account routes are hash routes at the site root.
export const REPO = 'https://github.com/gcharpe1604/ai_agent_debugger'

export const FOOTER = [
  {
    title: 'Product',
    links: [
      { label: 'Sign up', href: '/#/account/register' },
      { label: 'Sign in', href: '/#/account/login' },
      { label: 'Dashboard', href: '/docs/product/dashboard/' },
    ],
  },
  {
    title: 'Docs',
    links: [
      { label: 'Quickstart', href: '/docs/get-started/quickstart/' },
      { label: 'TraceSession', href: '/docs/sdk/trace-session/' },
      { label: 'Errors and retries', href: '/docs/concepts/errors-and-retries/' },
      { label: 'Ingest API', href: '/docs/api/ingest/' },
    ],
  },
  {
    title: 'Resources',
    links: [
      { label: 'GitHub', href: REPO, external: true },
      { label: 'Self-hosting', href: '/docs/self-hosting/docker-compose/' },
      { label: 'Limits', href: '/docs/limits/' },
    ],
  },
]
