// Agent Debugger docs: an Astro Starlight site served at /docs/.
// The build goes to dist/docs/, so dist/ can be served as a site root:
// Caddy copies dist/docs to /srv/docs, and a Vercel project serves dist/.
import { defineConfig, passthroughImageService } from 'astro/config'
import starlight from '@astrojs/starlight'
import starlightLinksValidator from 'starlight-links-validator'

const REPO = 'https://github.com/gcharpe1604/ai_agent_debugger'

export default defineConfig({
  base: '/docs',
  outDir: './dist/docs',
  trailingSlash: 'ignore',
  // No raster images in the docs, so no sharp dependency.
  image: { service: passthroughImageService() },
  // theme.css imports the app's tokens from ../frontend; let the dev server read them.
  vite: { server: { fs: { allow: ['.', '../frontend/src/styles'] } } },
  integrations: [
    starlight({
      title: 'Agent Debugger',
      favicon: '/favicon.svg',
      social: [{ icon: 'github', label: 'GitHub', href: REPO }],
      editLink: { baseUrl: `${REPO}/edit/main/docs-site/` },
      pagefind: true,
      // Fails the build on a broken internal link or heading anchor.
      plugins: [starlightLinksValidator()],
      lastUpdated: false,
      customCss: [
        '@fontsource-variable/inter',
        '@fontsource/jetbrains-mono/400.css',
        './src/styles/theme.css',
      ],
      components: {
        // Adds the "Open app" link next to the GitHub icon.
        SocialIcons: './src/components/HeaderLinks.astro',
      },
      sidebar: [
        { label: 'Overview', link: '/' },
        { label: 'Get started', items: ['get-started/quickstart'] },
        {
          label: 'Python SDK',
          items: ['sdk/trace-session', 'sdk/opentelemetry', 'sdk/capture-and-redaction'],
        },
        {
          label: 'Concepts',
          items: ['concepts/runs-and-spans', 'concepts/errors-and-retries', 'concepts/payloads'],
        },
        {
          label: 'Product',
          items: ['product/dashboard', 'product/tracing', 'product/trace-view', 'product/settings'],
        },
        {
          label: 'API reference',
          items: ['api/ingest', 'api/accounts', 'api/reading-runs', 'api/errors'],
        },
        {
          label: 'Self-hosting',
          items: ['self-hosting/docker-compose', 'self-hosting/configuration', 'self-hosting/upgrade-and-backup'],
        },
        { label: 'Limits and roadmap', link: '/limits/' },
      ],
    }),
  ],
})
