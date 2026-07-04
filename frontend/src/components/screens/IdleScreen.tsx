/**
 * Screen A — Idle / Landing (SPEC.md §5.1).
 *
 * Presentational only: gestures (swipe down -> Search & Settings, swipe
 * up -> Saved List) are wired by Task 4A; this component exposes the
 * tap/keyboard-reachable affordances that stand in for those gestures
 * per §13.1's tap/keyboard-parity requirement, via plain `onClick`
 * handlers the parent wires up however it wires real gestures.
 */
export interface IdleScreenProps {
  /** Whether anything has been saved this session (§5.1: the saved-list
   *  affordance is visually de-emphasized/disabled when empty). */
  hasSavedItems: boolean;
  onOpenSearch: () => void;
  /** Called when the user taps/activates the (possibly disabled) saved-list
   *  affordance. Per §5.1, when empty this should surface a "Nothing saved
   *  yet" no-op toast rather than navigating — that toast is the caller's
   *  concern (shared toast mechanism), this component just reports intent. */
  onOpenSaved: () => void;
}

export function IdleScreen({
  hasSavedItems,
  onOpenSearch,
  onOpenSaved,
}: IdleScreenProps) {
  return (
    <div className="flex h-full min-h-screen flex-col items-center justify-between bg-white px-6 py-10 text-slate-900">
      <button
        type="button"
        onClick={onOpenSearch}
        className="flex flex-col items-center text-sm text-slate-500"
        aria-label="Swipe down to search"
      >
        <span aria-hidden="true">⌄</span>
        <span>swipe down to search</span>
      </button>

      <div className="flex flex-col items-center gap-4">
        <h1 className="animate-pulse text-4xl font-semibold tracking-wide">
          LitList
        </h1>
        <p className="max-w-xs text-center text-slate-600">
          Swipe down to search PubMed and start listening.
        </p>
      </div>

      <button
        type="button"
        onClick={onOpenSaved}
        disabled={!hasSavedItems}
        aria-label="Swipe up for saved list"
        aria-disabled={!hasSavedItems}
        className={
          "flex flex-col items-center text-sm " +
          (hasSavedItems
            ? "text-slate-500"
            : "cursor-default text-slate-300")
        }
      >
        <span aria-hidden="true">⌃</span>
        <span>
          swipe up for saved list
          {!hasSavedItems ? " (disabled — empty)" : null}
        </span>
      </button>
    </div>
  );
}
