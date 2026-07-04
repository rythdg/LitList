/**
 * Renders a paper's abstract as an array of React elements, one per
 * segment, with the currently-playing sentence highlighted.
 *
 * SPEC.md §6.5 / §11.3 hard requirement: `display_text` is untrusted
 * external (PubMed) text, so it is rendered exclusively as React child
 * text nodes (`<span>{text}</span>`) — never via `dangerouslySetInnerHTML`
 * or string-concatenated markup. This is the fix for a real stored-XSS
 * path found during the spec's security review; do not "simplify" this
 * back to an HTML string.
 *
 * This component only *renders* the sentence-index-driven highlight; it
 * never computes segmentation or pause timing itself (that's the
 * backend tokenizer / usePlaybackEngine's job per §11.3 — this component
 * takes `segments` and `highlightedIndex` as plain props).
 */
import type { AbstractSegment } from "./types";

export interface SegmentedAbstractProps {
  segments: AbstractSegment[];
  /** Index into `segments` currently highlighted, or `null` if playback
   *  hasn't started / isn't applicable to this render (e.g. static demo). */
  highlightedIndex?: number | null;
}

export function SegmentedAbstract({
  segments,
  highlightedIndex = null,
}: SegmentedAbstractProps) {
  return (
    <p data-testid="segmented-abstract">
      {segments.map((segment) => (
        <span
          key={segment.index}
          data-testid={`segment-${segment.index}`}
          className={
            segment.kind === "section_header"
              ? "mt-2 block font-semibold"
              : segment.index === highlightedIndex
                ? "bg-yellow-200"
                : undefined
          }
        >
          {segment.display_text}
          {segment.kind === "sentence" ? " " : null}
        </span>
      ))}
    </p>
  );
}
