/**
 * Local presentational types for Task 2B's screen components (SPEC.md §5).
 *
 * As of Task 4A, `Paper`/`QueueItem`/`SavedItem` are direct aliases of
 * the real, CONTRACTS.md §5-pinned `frontend/src/api/types.ts` shapes
 * (flat objects — no nested `paper`/`authors[]`) rather than a second,
 * independently-invented type set. This file previously had its own
 * `Paper`/`QueueItem` shapes (nested `paper` object, a full `authors[]`
 * array, `last_author: Author | null`, `publication_types: string[]`)
 * that drifted from both the real backend response *and* from Task 2C's
 * `api/types.ts` — found and fixed during Task 4A's wiring pass (see
 * CONTRACTS.md's change log and this repo's
 * senior-fullstack-developer.build.log, "TASK 4A — PIVOT"). Consolidating
 * on one shape here removes the class of bug where these two files could
 * silently diverge again.
 */
import type {
  AbstractSegment as ApiAbstractSegment,
  ApiErrorBody,
  PauseClass as ApiPauseClass,
  QueueItem as ApiQueueItem,
  ReadAloudField,
  SavedItem as ApiSavedItem,
  SegmentedAbstractResponse as ApiSegmentedAbstractResponse,
  SegmentKind as ApiSegmentKind,
} from "../../api/types";

/** A paper-in-context as rendered by the Stack/Saved screens — the
 * fields common to both `QueueItem` and `SavedItem` (CONTRACTS.md §5).
 * Passing a real `QueueItem` or `SavedItem` here is always valid (both
 * are supersets of this shape). */
export type Paper = Pick<
  ApiQueueItem,
  "pmid" | "title" | "last_author" | "journal" | "pub_date" | "doi" | "citation_count" | "retracted"
>;

export function isRetracted(paper: Pick<Paper, "retracted">): boolean {
  return paper.retracted;
}

export type Decision = ApiQueueItem["decision"];

export type QueueItem = ApiQueueItem;
export type SavedItem = ApiSavedItem;

/** CONTRACTS.md §1 — pinned by Task 0.2, consumed (not recomputed) here. */
export type PauseClass = ApiPauseClass;
export type SegmentKind = ApiSegmentKind;
export type AbstractSegment = ApiAbstractSegment;
export type SegmentedAbstractResponse = ApiSegmentedAbstractResponse;

export type SortOption = "relevance" | "recency" | "citations";
export type DefaultSwipeBehavior = "interested" | "not_interested";

/** SPEC.md §3.2.C caps `read_aloud_fields` at exactly `{last_author,
 * journal, pub_date}` — matches `api/types.ts`'s `ReadAloudField` and
 * `state/searchDraftStore.ts`'s `readAloudFields: ReadAloudField[]`
 * exactly (an earlier version of this type had a 4th `all_authors`
 * toggle with no backing field anywhere; dropped during Task 4A's
 * wiring pass). */
export interface SearchSettings {
  query: string;
  sort: SortOption;
  read_aloud_fields: ReadAloudField[];
  default_swipe_behavior: DefaultSwipeBehavior;
  speed: number;
}

export type { ReadAloudField };

/** CONTRACTS.md §2 — pinned API error shape, project-wide. */
export interface ApiError {
  error: ApiErrorBody;
}
