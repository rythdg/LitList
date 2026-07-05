import type { Page } from "@playwright/test";

/**
 * Flips on the browser-side MSW worker (`src/api/mocks/browser.ts`,
 * reusing Task 2C's real `handlers`/fixtures) for a Playwright page,
 * *before* the app's own JS runs — `main.tsx` checks this exact global
 * before deciding whether to start the worker or hit the real backend.
 *
 * Call this before `page.goto(...)` for any "Playwright+MSW" journey
 * test (SPEC.md §15.3/§15.10); omit it entirely for a real-backend
 * Playwright test.
 */
export async function useMswInBrowser(page: Page): Promise<void> {
  await page.addInitScript(() => {
    (window as unknown as { __LITLIST_E2E_USE_MSW__?: boolean }).__LITLIST_E2E_USE_MSW__ = true;
  });
}

/**
 * Task 4B addition: seeds `e2eHandlers.ts`'s in-memory Zotero connection
 * state as already-connected *before* the app's first render. There is
 * no real Zotero OAuth provider to complete in an MSW-mocked journey
 * (that round-trip is covered by the backend's own contract test plus
 * `useZoteroPushFlowController`'s RTL+MSW tests) — this lets a
 * Playwright journey exercise everything *after* the connect step
 * (collection choice, push success/failure) against a real running app
 * instead. Must be called before `page.goto(...)`, same as
 * `useMswInBrowser`.
 */
export async function useZoteroConnectedInBrowser(page: Page): Promise<void> {
  await page.addInitScript(() => {
    (
      window as unknown as { __LITLIST_E2E_ZOTERO_CONNECTED__?: boolean }
    ).__LITLIST_E2E_ZOTERO_CONNECTED__ = true;
  });
}

export type ZoteroPushMode = "success" | "partial-failure" | "connection-failure";

/** Task 4B addition: selects which `POST /zotero/push` behavior
 * `e2eHandlers.ts` simulates for this page (defaults to `"success"` when
 * never called) — lets one spec file cover BuildPlan.md's three cited
 * scenarios (success/connection-failure/push-failure) against the same
 * stateful mock backend. Must be called before `page.goto(...)`. */
export async function useZoteroPushMode(page: Page, mode: ZoteroPushMode): Promise<void> {
  await page.addInitScript((injectedMode) => {
    (
      window as unknown as { __LITLIST_E2E_ZOTERO_PUSH_MODE__?: string }
    ).__LITLIST_E2E_ZOTERO_PUSH_MODE__ = injectedMode;
  }, mode);
}
