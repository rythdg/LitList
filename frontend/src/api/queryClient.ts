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
    },
  },
});
