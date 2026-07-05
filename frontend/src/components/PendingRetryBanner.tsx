/**
 * Adversarial-review fix (Finding 2, "TASK 4C SEC15.6 FOLLOW-UP REVIEW"):
 * a minimal, always-mounted signal for `retryQueueStore`'s contents
 * (SPEC.md §4.5 point 4, §5.5) — before this, a decision queued for
 * retry (kept optimistically, card already advanced past it) was
 * genuinely indistinguishable from a successfully-saved one; there was
 * no screen anywhere that read `retryQueueStore`'s state. Mounted
 * unconditionally in `App.tsx`, the same pattern as
 * `CookieConsentNotice` (§10.2) — a persistent, dismiss-per-item strip
 * rather than a modal, since a pending/failed background sync shouldn't
 * block the rest of the app.
 *
 * Deliberately generic (mirrors `retryQueueStore`'s own "doesn't know
 * about decisions/Zotero/any specific endpoint" design) — it renders
 * whatever `items`/`failedItems` currently hold, regardless of which
 * producer (`api/decisions.ts` today) put them there.
 */
import { useRetryQueueStore } from "../state/retryQueueStore";

export function PendingRetryBanner() {
  const items = useRetryQueueStore((state) => state.items);
  const failedItems = useRetryQueueStore((state) => state.failedItems);
  const isRetrying = useRetryQueueStore((state) => state.isRetrying);
  const retryAll = useRetryQueueStore((state) => state.retryAll);
  const dismissFailed = useRetryQueueStore((state) => state.dismissFailed);

  if (items.length === 0 && failedItems.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      {items.length > 0 ? (
        <div
          role="status"
          data-testid="pending-retry-banner"
          className="flex items-center justify-between gap-3 bg-amber-100 p-3 text-sm text-amber-900"
        >
          <p>
            {items.length === 1
              ? "1 change is pending — will retry when back online."
              : `${items.length} changes are pending — will retry when back online.`}
          </p>
          <button
            type="button"
            onClick={() => void retryAll()}
            disabled={isRetrying}
            className="shrink-0 rounded border border-amber-900/40 px-3 py-1 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isRetrying ? "Retrying…" : "Retry now"}
          </button>
        </div>
      ) : null}

      {failedItems.map((item) => (
        <div
          key={item.id}
          role="alert"
          data-testid="failed-retry-item"
          className="flex items-center justify-between gap-3 bg-red-100 p-3 text-sm text-red-900"
        >
          <p>
            Couldn&rsquo;t save: {item.label}. {item.message}
          </p>
          <button
            type="button"
            onClick={() => dismissFailed(item.id)}
            aria-label={`Dismiss failed: ${item.label}`}
            className="shrink-0 rounded border border-red-900/40 px-3 py-1"
          >
            Dismiss
          </button>
        </div>
      ))}
    </div>
  );
}
