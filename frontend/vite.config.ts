import { defineConfig } from 'vite'
import { configDefaults } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
// PWA plugin (vite-plugin-pwa) wired in by Task 2A (§11.1/§11.5): generates
// the manifest + a service worker that precaches the app shell only.
// Per §11.5, PubMed/paper data is explicitly *not* cached here — that data
// already has a server-side cache (Paper, §9.2); TanStack Query's in-memory
// cache (Task 2C) is what keeps already-fetched papers available offline
// mid-session, not the service worker.
//
// `base` (Task 5B, §12.4): configurable via the VITE_BASE_PATH build-time
// env var rather than hardcoded, and defaults to root ('/') — the correct
// value for local dev/preview *and* for §12.2's promised zero-code-change
// migration to Cloudflare Pages/a custom domain later, both of which serve
// from root, not a subpath. GitHub Pages is the one deploy target that
// needs a non-root value, since it serves this repo as a *project* site —
// https://rythdg.github.io/LitList/ — so every asset URL and the PWA
// manifest's start_url/scope must be prefixed with the repo name there or
// asset loading (and SW registration) breaks under that subpath.
// `.github/workflows/deploy.yml` sets VITE_BASE_PATH=/LitList/ only for
// its `npm run build` step, specifically because it deploys to GitHub
// Pages — not baked in here as the repo's default, so switching hosts
// later is genuinely just a one-line CI env var change, not a code change.
const base = process.env.VITE_BASE_PATH || '/'

export default defineConfig({
  base,
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      // App-shell precache only (JS/CSS/HTML/icons) — vite-plugin-pwa's
      // default globPatterns already exclude API responses since those
      // are never bundled assets; no paper/queue data is ever precached.
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff2}'],
        navigateFallbackDenylist: [/^\/api\//, /^\/oauth\//],
      },
      manifest: {
        name: 'LitList',
        short_name: 'LitList',
        description:
          'A free PWA that turns a PubMed search into a swipeable, TTS-narrated queue of papers.',
        theme_color: '#1e293b',
        background_color: '#ffffff',
        display: 'standalone',
        start_url: base,
        scope: base,
        icons: [
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: 'pwa-512x512-maskable.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
    }),
  ],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // e2e/ holds Playwright specs (playwright.config.ts, §15.3/§15.10) —
    // they use @playwright/test's own `test`/`test.describe`, not
    // Vitest's, and must run only via `npx playwright test`, never swept
    // up by `vitest run`'s default include glob (which otherwise matches
    // any `*.spec.ts` file in the project, Playwright's included).
    exclude: [...configDefaults.exclude, 'e2e/**', 'e2e-live/**'],
  },
})
