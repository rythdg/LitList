import type { ApiErrorBody } from "../api/types";
import { getErrorCopy, type ErrorContext } from "./errorCopy";

/**
 * Shared error-rendering component (Task 4C, §11.7) consuming
 * CONTRACTS.md §2's pinned `{code, message}` error shape. One structure,
 * specialized only by copy per context (§4.3 generic / §4.4+§5.5 Zotero
 * push / §4.5 offline / §13.6 external-downtime) — every TanStack Query
 * error state in the app should render through this component rather
 * than each screen inventing its own error markup.
 */
export interface ErrorStateProps {
  /** CONTRACTS.md §2's inner error object, or `null`/`undefined` when
   *  there's no server-reported error to show (e.g. a purely
   *  client-detected offline state with no failed request yet). */
  error?: ApiErrorBody | null;
  /** Client-detected connectivity state (`networkStore.isOnline` negated)
   *  — takes priority over `error.code`, see `errorCopy.ts`. */
  isOffline?: boolean;
  context?: ErrorContext;
  /** §5.3a's `empty_results` context only — the search query that came
   *  back with zero results, interpolated into the copy by `errorCopy.ts`. */
  query?: string;
  onRetry?: () => void;
  /** Overrides the default "Retry"/"Retry now" button label — e.g.
   *  §5.3a's "Swipe down to try a different search." affordance, which is
   *  structurally the same retry action as every other context but reads
   *  differently. Structure (one button, one `onRetry` handler) stays
   *  identical; only the label is context-specific, matching this
   *  component's "copy-only specialization" rule. */
  retryLabel?: string;
  /** Task 4B post-review fix (§5.5 Step 3b, ZoteroPushFlow's failure
   *  step): disables the Retry button while the retried action is
   *  already in flight, so a rapid double-click can't fire two
   *  concurrent requests for whatever `onRetry` triggers. Structure-only
   *  addition — no other context needs this yet, but it's generic
   *  (any `onRetry` consumer can pass it), not Zotero-specific. */
  retryDisabled?: boolean;
  /** §4.4/§5.5: Zotero push failure always offers a CSV fallback
   *  alongside retry, never retry alone. */
  onDownloadCsv?: () => void;
  className?: string;
}

export function ErrorState({
  error = null,
  isOffline = false,
  context = "generic",
  query,
  onRetry,
  retryLabel,
  retryDisabled = false,
  onDownloadCsv,
  className,
}: ErrorStateProps) {
  const { title, message } = getErrorCopy({ context, error, isOffline, query });

  return (
    <div
      role="alert"
      data-testid="error-state"
      data-context={context}
      data-code={error?.code ?? (isOffline ? "offline" : "none")}
      className={
        "flex flex-col gap-2 rounded border border-slate-200 p-3 text-slate-900" +
        (className ? ` ${className}` : "")
      }
    >
      <p className="font-medium">{title}</p>
      <p className="text-sm text-slate-600">{message}</p>
      {onRetry || onDownloadCsv ? (
        <div className="flex gap-2">
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              disabled={retryDisabled}
              className="rounded bg-slate-900 px-4 py-2 font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {retryLabel ?? (isOffline ? "Retry now" : "Retry")}
            </button>
          ) : null}
          {onDownloadCsv ? (
            <button
              type="button"
              onClick={onDownloadCsv}
              className="rounded border border-slate-300 px-4 py-2"
            >
              Download CSV
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
