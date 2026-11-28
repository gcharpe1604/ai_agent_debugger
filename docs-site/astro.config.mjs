// Agent Debugger docs: an Astro Starlight site served at /docs/.
// The build goes to dist/docs/, so dist/ can be served as a site root:
// Caddy copies dist/docs to /srv/docs, and a Vercel project serves dist/.
import { defineConfig, passthroughImageService } from 'astro/config'
import starlight from '@astrojs/starlight'
import starlightLinksValidator from 'starlight-links-validator'
import { tokenThemes } from './src/code-themes.mjs'

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
      // The landing page's chrome (docs/frontend/landing-spec.md): its header, a
      // 1280 px frame with hairline column rules and a sticky sidebar, its footer,
      // and its theme pill on the app's own theme key.
      components: {
        Header: './src/components/Header.astro',
        PageFrame: './src/components/PageFrame.astro',
        MobileMenuFooter: './src/components/MobileMenuFooter.astro',
        ThemeProvider: './src/components/ThemeProvider.astro',
        ThemeSelect: './src/components/ThemeSelect.astro',
        // Mono kicker (sidebar section, or "Docs") above each page title.
        PageTitle: './src/components/PageTitle.astro',
      },
      // Code blocks as the landing page's code card: token colours, mono 13/22,
      // a tab row for titles (no terminal window chrome), no shadow.
      expressiveCode: {
        themes: tokenThemes(),
        minSyntaxHighlightingColorContrast: 0,
        // Long lines wrap instead of scrolling sideways (spec §4).
        defaultProps: { frame: 'code', wrap: true },
        styleOverrides: {
          borderRadius: '8px',
          borderWidth: '1px',
          borderColor: 'var(--adbg-border-strong)',
          codeBackground: 'var(--adbg-surface-alt)',
          codeFontFamily: 'var(--font-mono)',
          codeFontSize: '13px',
          codeLineHeight: '22px',
          codePaddingBlock: '16px',
          codePaddingInline: '16px',
          uiFontFamily: 'var(--font-mono)',
          uiFontSize: '12px',
          // 12 px × 1.65 line height + 2 × 10 px = a 40 px tab, as on the landing page.
          uiPaddingBlock: '10px',
          uiPaddingInline: '16px',
          frames: {
            frameBoxShadowCssValue: 'none',
            editorTabBarBackground: 'var(--color-bg)',
            editorTabBarBorderColor: 'var(--adbg-border-strong)',
            editorTabBarBorderBottomColor: 'var(--color-border)',
            editorTabBorderRadius: '0px',
            editorActiveTabBackground: 'var(--adbg-surface-alt)',
            editorActiveTabForeground: 'var(--color-text)',
            editorActiveTabBorderColor: 'var(--color-border)',
            editorActiveTabIndicatorTopColor: 'transparent',
            editorActiveTabIndicatorBottomColor: 'transparent',
            editorActiveTabIndicatorHeight: '0px',
            inlineButtonBackground: 'var(--color-bg)',
            inlineButtonForeground: 'var(--color-text-secondary)',
            inlineButtonBorder: 'var(--adbg-border-strong)',
            tooltipSuccessBackground: 'var(--color-success)',
            tooltipSuccessForeground: 'var(--color-bg)',
          },
        },
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
