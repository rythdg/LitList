import type { ApiErrorBody } from "../api/types";

/**
 * Contexts the shared `ErrorState` component (Task 4C, §11.7) can render.
 * Per BuildPlan.md's brief: specialized only by *copy*, never by
 * structure — every context renders through the same component shape
 * (title + message + optional retry/CSV-fallback actions).
 */
export type ErrorContext = "generic" | "zotero_push" | "empty_results";

export interface ErrorCopy {
  title: string;
  message: string;
}

const GENERIC_MESSAGE = "Something went wrong. Please try again.";

/**
 * Resolves the (title, message) pair for a given context/error/offline
 * combination. Exported as a plain function (not just used inside the
 * component) so it has its own direct unit test asserting the two
 * SPEC.md-mandated distinctions never collapse into each other:
 *
 * - §4.5 "you're offline" vs. §13.6 "external service unavailable"
 *   (CONTRACTS.md §2's `service_unavailable` code) are different problems
 *   with different user actions, and must not share copy.
 * - `isOffline` always wins over any server-reported error code, because
 *   if the request never reached the network, the code (if any is even
 *   present) isn't the real story.
 *
 * `query` is only meaningful for the `empty_results` context (§5.3a) —
 * the zero-results screen's copy names the query that came back empty.
 */
export function getErrorCopy(params: {
  context?: ErrorContext;
  error?: ApiErrorBody | null;
  isOffline?: boolean;
  query?: string;
}): ErrorCopy {
  const { context = "generic", error = null, isOffline = false, query } = params;

  // §4.5: the user's own connectivity is down. Takes priority over any
  // error code, since offline requests may not have reached the server
  // (or a server-side timeout looks identical to `service_unavailable`)
  // but the actionable advice to the user is completely different.
  if (isOffline) {
    return context === "zotero_push"
      ? {
          title: "You're offline",
          message: "Pending — will retry when back online.",
        }
      : {
          title: "You're offline",
          message:
            "New searches, further pages, and Zotero actions will resume automatically once you're back online. Anything already loaded keeps working.",
        };
  }

  // §13.6: an external dependency (PubMed/iCite/Zotero) is down while the
  // user's own connection is fine — distinct copy from the offline case
  // above, driven by CONTRACTS.md §2's `service_unavailable` code.
  if (error?.code === "service_unavailable") {
    return {
      title: "Temporarily unavailable",
      message:
        error.message ||
        "This service is currently unavailable. Please try again shortly.",
    };
  }

  if (context === "zotero_push") {
    const isConnectionIssue =
      error?.code === "zotero_not_connected" ||
      error?.code === "zotero_session_mismatch";
    return {
      title: isConnectionIssue
        ? "Couldn't connect to Zotero"
        : "Couldn't save to Zotero",
      message: `Nothing was lost — your list is unchanged. ${
        error?.message ?? GENERIC_MESSAGE
      }`,
    };
  }

  // §4.3/§5.3a: zero PubMed results for the query just run. Not a
  // CONTRACTS.md §2-shaped error at all (the request succeeded; the
  // result set is just empty) — still routed through this single copy
  // source so the wording stays in one place rather than being
  // hardcoded a second time in the screen that renders it.
  if (context === "empty_results") {
    return {
      title: "No papers matched",
      message: query ? `"${query}".` : "Try a different search.",
    };
  }

  return {
    title: "Something went wrong",
    message: error?.message ?? GENERIC_MESSAGE,
  };
}
