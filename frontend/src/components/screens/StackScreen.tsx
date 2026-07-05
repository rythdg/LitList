/**
 * Screen C — Stack Screen, the home surface (SPEC.md §5.3, §5.3a, §13.4).
 *
 * Presentational only. The swipe gesture itself (Framer Motion drag) is
 * wired by Task 4A (§11.4) — this component provides the tap/click and
 * keyboard-equivalent paths (§13.1) and calls the *same* `onDecide`
 * callback either way, so the parent never has to reconcile divergent
 * call shapes from different input methods.
 */
import { useEffect } from "react";
import { motion } from "framer-motion";
import { useSwipeToDecide } from "../../gestures/useSwipeToDecide";
import { SegmentedAbstract } from "./SegmentedAbstract";
import { isRetracted, type AbstractSegment, type Paper } from "./types";

export type DecisionSource = "swipe" | "tap" | "keyboard";

export interface StackScreenProps {
  currentPaper: Paper;
  nextPaper: Paper | null;
  segments: AbstractSegment[];
  highlightedIndex: number | null;
  /** §5.3: the abstract stays collapsed/greyed until playback starts. */
  isPlaying: boolean;
  isMuted: boolean;
  onDecide: (
    decision: "interested" | "not_interested",
    source: DecisionSource,
  ) => void;
  onTogglePlay: () => void;
  onToggleMute: () => void;
  onOpenSearch: () => void;
  onOpenSaved: () => void;
  /** Screen-reader-facing status text (§13.1's aria-live requirement) —
   *  e.g. "Now playing: <title>" or "Marked interested". Parent owns the
   *  wording/timing; this component just renders it into a live region. */
  liveAnnouncement?: string;
  /** True while the caller's decision function (§11.4 — PATCH +
   *  optimistic update, `App.tsx`'s `decide()`) is still in flight for
   *  this card, e.g. `updateDecision.isPending`. Threaded straight
   *  through to `useSwipeToDecide`'s `disabled` option so a fast
   *  double-swipe/double-tap/double-keypress can't fire a second
   *  decision for the same paper (adversarial review, "TASK 4A REVIEW" —
   *  the hook's own guard existed and was tested but nothing ever wired
   *  this through). */
  isDecisionPending?: boolean;
}

function metadataLine(paper: Paper): string {
  const parts: string[] = [];
  if (paper.last_author) {
    parts.push(`${paper.last_author} et al.`);
  }
  if (paper.journal) parts.push(paper.journal);
  if (paper.pub_date) parts.push(paper.pub_date);
  return parts.join(" · ");
}

export function StackScreen({
  currentPaper,
  nextPaper,
  segments,
  highlightedIndex,
  isPlaying,
  isMuted,
  onDecide,
  onTogglePlay,
  onToggleMute,
  onOpenSearch,
  onOpenSaved,
  liveAnnouncement,
  isDecisionPending = false,
}: StackScreenProps) {
  // §11.4/§15.10: swipe (drag), tap, and keyboard are three triggers into
  // one function — `triggerDecision`/the drag gesture's own commit both
  // funnel into `useSwipeToDecide`'s single `commitExit`, which plays the
  // same exit animation and then calls `onDecide` (the real decision
  // function, owned by the caller) regardless of which input fired it.
  const { rotate, likeOpacity, nopeOpacity, controls, dragProps, triggerDecision } =
    useSwipeToDecide({ onDecide, disabled: isDecisionPending });

  // §13.1 keyboard shortcuts, routed through the exact same
  // `triggerDecision` path as the tap controls below — never a divergent
  // path from swipe.
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      switch (event.key) {
        case "ArrowRight":
          triggerDecision("interested", "keyboard");
          break;
        case "ArrowLeft":
          triggerDecision("not_interested", "keyboard");
          break;
        case " ":
        case "Spacebar":
          event.preventDefault();
          onTogglePlay();
          break;
        case "ArrowDown":
          onOpenSearch();
          break;
        case "ArrowUp":
          onOpenSaved();
          break;
        default:
          break;
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [triggerDecision, onTogglePlay, onOpenSearch, onOpenSaved]);

  const retracted = isRetracted(currentPaper);

  return (
    <div className="flex min-h-screen flex-col gap-4 bg-white p-4 text-slate-900">
      <div aria-live="polite" className="sr-only" data-testid="live-region">
        {liveAnnouncement}
      </div>

      <button
        type="button"
        onClick={onOpenSearch}
        aria-label="Swipe down for search"
        className="text-sm text-slate-500"
      >
        ⌄ swipe down for search
      </button>

      <motion.div
        className="relative flex flex-1 touch-pan-y flex-col gap-3"
        data-testid="current-card"
        style={{ rotate }}
        animate={controls}
        {...dragProps}
      >
        <motion.span
          aria-hidden="true"
          data-testid="like-overlay"
          className="pointer-events-none absolute right-2 top-2 rounded border-2 border-emerald-500 px-2 py-1 text-sm font-bold text-emerald-600"
          style={{ opacity: likeOpacity }}
        >
          ♥ INTERESTED
        </motion.span>
        <motion.span
          aria-hidden="true"
          data-testid="nope-overlay"
          className="pointer-events-none absolute left-2 top-2 rounded border-2 border-red-500 px-2 py-1 text-sm font-bold text-red-600"
          style={{ opacity: nopeOpacity }}
        >
          ✕ SKIP
        </motion.span>

        {retracted ? (
          <span
            role="status"
            data-testid="retracted-badge"
            className="inline-block w-fit rounded bg-red-100 px-2 py-1 text-sm font-medium text-red-800"
          >
            ⚠ Retracted
          </span>
        ) : null}

        <h2 className="text-xl font-semibold">{currentPaper.title}</h2>

        <div
          className={
            "rounded border border-slate-200 p-3 " +
            (isPlaying ? "" : "text-slate-300")
          }
          data-testid="abstract-area"
          aria-hidden={!isPlaying}
        >
          <SegmentedAbstract
            segments={segments}
            highlightedIndex={isPlaying ? highlightedIndex : null}
          />
        </div>

        <p className="text-sm text-slate-600">{metadataLine(currentPaper)}</p>

        {nextPaper ? (
          <div
            className="rounded border border-dashed border-slate-300 p-2 text-sm text-slate-500"
            data-testid="next-up-preview"
          >
            Next: &quot;{nextPaper.title}&quot;
          </div>
        ) : null}
      </motion.div>

      <div className="flex justify-center gap-4">
        <button
          type="button"
          onClick={() => triggerDecision("not_interested", "tap")}
          aria-label="Not interested"
          className="rounded-full border border-slate-300 px-4 py-2"
        >
          ✕ Skip
        </button>
        <button
          type="button"
          onClick={() => triggerDecision("interested", "tap")}
          aria-label="Interested"
          className="rounded-full border border-slate-300 px-4 py-2"
        >
          ♥ Interested
        </button>
      </div>

      <div className="flex items-center justify-center gap-4">
        <button
          type="button"
          onClick={onTogglePlay}
          aria-label={isPlaying ? "Pause" : "Play"}
          className="flex h-14 w-14 items-center justify-center rounded-full bg-slate-900 text-white"
        >
          {isPlaying ? "⏸" : "▶"}
        </button>
        <button
          type="button"
          onClick={onToggleMute}
          aria-label={isMuted ? "Unmute" : "Mute"}
          className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-300"
        >
          {isMuted ? "🔇" : "🔊"}
        </button>
      </div>

      <button
        type="button"
        onClick={onOpenSaved}
        aria-label="Swipe up for saved list"
        className="text-sm text-slate-500"
      >
        ⌃ swipe up for saved list
      </button>
    </div>
  );
}
