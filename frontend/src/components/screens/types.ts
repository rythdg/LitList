/**
 * Local presentational types for Task 2B's screen components (SPEC.md §5).
 *
 * These mirror SPEC.md §9.2's `Paper`/`QueueDecision` entity fields and
 * CONTRACTS.md's `AbstractSegment`/`SegmentedAbstractResponse` shapes.
 * CONTRACTS.md does not (yet) pin a `/queue`/`/saved` response shape —
 * that's Tier 3's job (Task 3A) — so these are Task 2B's own,
 * intentionally close to §9.2's field names so a later reshape (Task 2C/
 * 4A wiring real endpoints) is a rename, not a redesign. If Tier 3 lands
 * a shape that meaningfully diverges from this, that's a CONTRACTS.md gap
 * to fix, not something to quietly paper over here.
 */

export interface Author {
  first_name: string;
  last_name: string;
}

/** SPEC.md §9.2 `Paper` — a cached, session-independent PubMed record. */
export interface Paper {
  pmid: string;
  title: string;
  authors: Author[];
  last_author: Author | null;
  journal: string;
  pub_date: string;
  /** Absent for many older PubMed records (§13.4) — omit, never fabricate. */
  doi: string | null;
  /** Untrusted external (PubMed) text — never render as raw HTML (§6.5/§11.3). */
  display_abstract: string;
  citation_count: number | null;
  /** Raw PubMed `PublicationType` values (§13.4) — used to derive the
   *  "⚠ Retracted" badge without the frontend re-deciding what "retracted"
   *  means beyond checking for this exact backend-supplied string. */
  publication_types: string[];
}

export function isRetracted(paper: Pick<Paper, "publication_types">): boolean {
  return paper.publication_types.includes("Retracted Publication");
}

export type Decision = "pending" | "interested" | "not_interested";

export interface QueueItem {
  paper: Paper;
  decision: Decision;
}

/** CONTRACTS.md §1 — pinned by Task 0.2, consumed (not recomputed) here. */
export type PauseClass = "structural" | "sentence";
export type SegmentKind = "section_header" | "sentence";

export interface AbstractSegment {
  index: number;
  kind: SegmentKind;
  section_label: string | null;
  display_text: string;
  spoken_text: string;
  char_start: number;
  char_end: number;
  pause_class: PauseClass;
}

export interface SegmentedAbstractResponse {
  pmid: string;
  narration_unavailable: boolean;
  segments: AbstractSegment[];
}

export type SortOption = "relevance" | "recency" | "citations";
export type DefaultSwipeBehavior = "interested" | "not_interested";

export interface SearchSettings {
  query: string;
  sort: SortOption;
  read_aloud_fields: {
    last_author: boolean;
    all_authors: boolean;
    journal: boolean;
    pub_date: boolean;
  };
  default_swipe_behavior: DefaultSwipeBehavior;
  speed: number;
}

/** CONTRACTS.md §2 — pinned API error shape, project-wide. */
export interface ApiError {
  error: {
    code: string;
    message: string;
  };
}
