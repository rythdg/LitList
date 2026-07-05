import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./types";

/**
 * The one TanStack Query client for the app (SPEC.md §11.2 — server
 * state lives here, never duplicated in Zustand). `retry` is disabled
 * for the app-level `rate_limited`/`validation_error`/`not_found` codes
 * since retrying those without a changed input just repeats the same
 * failure; other errors (e.g. `service_unavailable`, network drops per
 * §11.5's offline behavior) fall back to TanStack Query's default
 * backoff retry.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (error instanceof ApiError) {
          const noRetryCodes = ["validation_error", "not_found", "zotero_session_mismatch"];
          if (noRetryCodes.includes(error.code)) {
            return false;
          }
        }
        return failureCount < 2;
      },
    },
    mutations: {
      retry: false,
      // Adversarial-review follow-up discovery (Findings 1/2 fix,
      // debugging the real-browser §15.6 Playwright coverage for them):
      // TanStack Query's default `networkMode: "online"` makes a
      // mutation *pause* (never actually call `mutationFn`, so `onError`
      // never runs) whenever its own internal `onlineManager` — which
      // listens to the exact same real `window` `online`/`offline`
      // events `state/offlineSync.ts` does — thinks the browser is
      // offline, then silently auto-resumes and retries the identical
      // request itself once back online. That's a second, independent
      // offline-retry mechanism reacting to the same signal our own
      // `state/retryQueueStore.ts` (§4.5 point 4) was purpose-built to
      // own, including this task's ApiError-vs-network-failure
      // distinction and the user-visible pending/failed surfacing —
      // TanStack's built-in pause bypasses all of that silently. Forcing
      // `networkMode: "always"` for mutations means a mutation always
      // actually attempts its real network call (and gets a real
      // success/`ApiError`/network-rejection back) regardless of
      // `onlineManager`'s own belief about connectivity, so
      // `retryQueueStore` remains the single, authoritative mechanism
      // for what happens next — consistent with §11.2's one-owner-per-
      // fact principle. Queries intentionally keep the default
      // `networkMode` (pausing an in-flight *read* while offline is
      // harmless and arguably correct; only mutations have a
      // side-effecting retry story this app needs to own itself).
      networkMode: "always",
    },
  },
});
