/**
 * Screen C — Empty results state (SPEC.md §5.3a, §4.3).
 *
 * No queue exists, so the play button is visibly disabled (greyed, no
 * functional tap response); only the swipe-down-to-search path is live.
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
      <p>
        No papers matched
        <br />
        &quot;{query}&quot;.
      </p>
      <button
        type="button"
        onClick={onOpenSearch}
        className="text-sm text-slate-500"
      >
        Swipe down to try a different search.
      </button>
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
