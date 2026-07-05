import { useUiStore } from "../state/uiStore";

/**
 * Cookie-consent notice (SPEC.md §10.2, §11.7). A simple, dismiss-once
 * banner — not a consent gate (the underlying session cookie is
 * strictly-necessary and already set regardless of this banner, §10.2) —
 * using the exact copy SPEC.md §10.2 suggests, naming the cookie's
 * actual narrow purpose rather than generic "we use cookies" boilerplate.
 * Dismissal is tracked in `uiStore` (local-only UI state, §11.2), which
 * Task 2C already scaffolded (`isCookieNoticeDismissed`/
 * `dismissCookieNotice`) — this component is what actually renders it.
 */
export function CookieConsentNotice() {
  const isDismissed = useUiStore((state) => state.isCookieNoticeDismissed);
  const dismiss = useUiStore((state) => state.dismissCookieNotice);

  if (isDismissed) return null;

  return (
    <div
      role="status"
      data-testid="cookie-consent-notice"
      className="flex items-center justify-between gap-3 bg-slate-900 p-3 text-sm text-white"
    >
      <p>
        LitList uses one cookie to remember your search settings and
        in-progress reading list on this device — no tracking, no ads,
        nothing shared with anyone. If you connect Zotero, the same
        cookie is what lets us remember that connection.
      </p>
      <button
        type="button"
        onClick={dismiss}
        aria-label="Dismiss cookie notice"
        className="shrink-0 rounded border border-white/40 px-3 py-1"
      >
        Got it
      </button>
    </div>
  );
}
