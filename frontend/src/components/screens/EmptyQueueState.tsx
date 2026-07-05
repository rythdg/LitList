import { ErrorState } from "../ErrorState";

/**
 * Screen C — Empty results state (SPEC.md §5.3a, §4.3).
 *
 * No queue exists, so the play button is visibly disabled (greyed, no
 * functional tap response); only the swipe-down-to-search path is live.
 * The "no papers matched" copy is rendered via the shared `ErrorState`/
 * `errorCopy.ts` (Task 4C, §11.7) `empty_results` context rather than a
 * second hardcoded copy of the same wording — a zero-result search isn't
 * a CONTRACTS.md §2-shaped error, but §5.3a is still one of the contexts
 * BuildPlan.md's Task 4C line names for this shared component, so it
 * goes through the same single copy source as every other context.
 */
export interface EmptyQueueStateProps {
  query: string;
  onOpenSearch: () => void;
}

export function EmptyQueueState({ query, onOpenSearch }: EmptyQueueStateProps) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-white p-6 text-center text-slate-900">
      <p className="text-slate-400" aria-hidden="true">
        (no results)
      </p>
      <ErrorState
        context="empty_results"
        query={query}
        onRetry={onOpenSearch}
        retryLabel="Swipe down to try a different search."
        className="items-center border-none p-0 text-center"
      />
      <button
        type="button"
        disabled
        aria-disabled="true"
        aria-label="Play (disabled, no queue)"
        title="Nothing to play yet"
        data-testid="disabled-play-button"
        className="flex h-14 w-14 cursor-not-allowed items-center justify-center rounded-full bg-slate-200 text-slate-400"
      >
        ▶
      </button>
    </div>
  );
}
