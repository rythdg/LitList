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

/**
 * SEC15.6 addition (offline-emulation follow-up to Task 4C, §4.5/§15.6):
 * flips `e2eHandlers.ts`'s `PATCH /decisions/{pmid}` mock between
 * succeeding and simulating a real network-level failure
 * (`HttpResponse.error()`) — the way an actual offline `fetch()`
 * rejection looks, distinct from a server-returned error. Unlike
 * `useZoteroPushMode` above (an init-script flag fixed for the whole
 * test), this is a live `page.evaluate` write so a spec can flip
 * connectivity *mid-session*, after the app has already loaded and the
 * user is mid-triage — see `e2eHandlers.ts`'s `isDecisionNetworkDown`
 * docstring for why this, rather than `context.setOffline`, is what
 * actually makes an MSW-mocked request fail.
 */
export async function setDecisionNetworkDown(page: Page, down: boolean): Promise<void> {
  await page.evaluate((value) => {
    (
      window as unknown as { __LITLIST_E2E_DECISION_NETWORK_DOWN__?: boolean }
    ).__LITLIST_E2E_DECISION_NETWORK_DOWN__ = value;
  }, down);
}

/**
 * SEC15.6 addition (§13.6 vs. §4.5 distinctness test): makes
 * `e2eHandlers.ts`'s `POST /search` return CONTRACTS.md §2's real
 * `service_unavailable` shape, simulating PubMed itself being down while
 * the user's own connection is fine — the opposite condition from
 * `setDecisionNetworkDown`. Must be called before `page.goto(...)`, same
 * as `useMswInBrowser`.
 */
export async function useSearchServiceUnavailable(page: Page): Promise<void> {
  await page.addInitScript(() => {
    (
      window as unknown as { __LITLIST_E2E_SEARCH_SERVICE_DOWN__?: boolean }
    ).__LITLIST_E2E_SEARCH_SERVICE_DOWN__ = true;
  });
}

/**
 * Dispatches the browser's real `online`/`offline` `window` events
 * (SEC15.6) — the exact signal `state/offlineSync.ts`'s real listener
 * (wired once from `main.tsx`) reacts to. Used instead of
 * `context.setOffline` for MSW-backed specs, since `context.setOffline`
 * only blocks real network sockets and has no effect on MSW's
 * Service-Worker-intercepted responses (see `e2eHandlers.ts`'s
 * `isDecisionNetworkDown` docstring) — but the app's *own*
 * connectivity-detection code only listens for these two DOM events
 * regardless of what causes them, so dispatching them directly still
 * exercises the real `offlineSync.ts`/`networkStore.ts` production path,
 * not a mock of it.
 */
export async function dispatchConnectivityEvent(page: Page, type: "online" | "offline"): Promise<void> {
  await page.evaluate((eventType) => {
    window.dispatchEvent(new Event(eventType));
  }, type);
}

/**
 * Adversarial-review fix follow-up (Finding 1's Playwright coverage):
 * makes `e2eHandlers.ts`'s `PATCH /decisions/{pmid}` return a real
 * CONTRACTS.md §2 `not_found` `ApiError` instead of succeeding or
 * network-failing — simulates "something genuinely changed server-side
 * while this decision sat queued" (distinct from `setDecisionNetworkDown`,
 * which simulates the connectivity problem that queued it in the first
 * place). Live-toggled the same way as `setDecisionNetworkDown`.
 */
export async function setDecisionNotFound(page: Page, notFound: boolean): Promise<void> {
  await page.evaluate((value) => {
    (
      window as unknown as { __LITLIST_E2E_DECISION_NOT_FOUND__?: boolean }
    ).__LITLIST_E2E_DECISION_NOT_FOUND__ = value;
  }, notFound);
}
