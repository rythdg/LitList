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
import { SegmentedAbstract } from "./SegmentedAbstract";
import { isRetracted, type AbstractSegment, type Paper } from "./types";

export type DecisionSource = "tap" | "keyboard";

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
}

function metadataLine(paper: Paper): string {
  const parts: string[] = [];
  if (paper.last_author) {
    parts.push(`${paper.last_author.last_name} et al.`);
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
}: StackScreenProps) {
  // §13.1 keyboard shortcuts, routed through the same single decision
  // function/callbacks as the tap controls below — never a divergent path.
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      switch (event.key) {
        case "ArrowRight":
          onDecide("interested", "keyboard");
          break;
        case "ArrowLeft":
          onDecide("not_interested", "keyboard");
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
  }, [onDecide, onTogglePlay, onOpenSearch, onOpenSaved]);

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

      <div className="flex flex-1 flex-col gap-3" data-testid="current-card">
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
      </div>

      <div className="flex justify-center gap-4">
        <button
          type="button"
          onClick={() => onDecide("not_interested", "tap")}
          aria-label="Not interested"
          className="rounded-full border border-slate-300 px-4 py-2"
        >
          ✕ Skip
        </button>
        <button
          type="button"
          onClick={() => onDecide("interested", "tap")}
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
