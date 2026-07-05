import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import { Root } from './routes/Root.tsx'
import { queryClient } from './api'
import { initOfflineSync } from './state'

// Routing here is deliberately minimal (§11.6) — see routes/Root.tsx for
// why a full router isn't introduced and how the one real route (the
// Zotero OAuth callback, Task 2A) is handled instead.
//
// The one TanStack Query client for the whole app (§11.2) is provided
// here, at the root, rather than inside `App.tsx` itself, so there is
// exactly one `QueryClient` instance for the app's real lifetime,
// matching `api/queryClient.ts`'s own "the one TanStack Query client"
// framing.

declare global {
  interface Window {
    /** Set only by Playwright's MSW-backed journey tests via
     *  `page.addInitScript` (see `e2e/support/mswBrowser.ts`) — never
     *  true in production or in the real-backend Playwright journeys.
     *  Gates whether the browser-side MSW worker (`api/mocks/browser.ts`,
     *  Task 2C's handlers) intercepts `/api/v1/...` calls before the app
     *  ever renders, so those tests never race a real network call. */
    __LITLIST_E2E_USE_MSW__?: boolean;
  }
}

async function bootstrap() {
  if (typeof window !== 'undefined' && window.__LITLIST_E2E_USE_MSW__) {
    const { worker } = await import('./api/mocks/browser')
    await worker.start({ onUnhandledRequest: 'bypass' })
  }

  // §4.5/§11.5: bridges real browser online/offline events into
  // `networkStore` and drains `retryQueueStore` on reconnect. Task 4C
  // built and unit-tested this (`state/offlineSync.ts`) but nothing ever
  // called it — this is the one real app entry point, called exactly
  // once for the app's lifetime (never inside `App.tsx`, which can
  // remount in tests without needing a duplicate `window` listener).
  initOfflineSync()

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <Root />
      </QueryClientProvider>
    </StrictMode>,
  )
}

void bootstrap()
