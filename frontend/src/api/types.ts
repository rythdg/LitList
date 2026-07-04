/**
 * Shared frontend/backend data shapes.
 *
 * The three shapes pinned in /CONTRACTS.md (segmented-abstract response,
 * API error, Zotero push per-item response) are transcribed verbatim
 * below — treat any real-backend mismatch against CONTRACTS.md as a bug
 * to report, not something to reshape around silently.
 *
 * Everything else here (search/queue/saved/settings/zotero-collections
 * shapes) is *not* pinned by CONTRACTS.md as of Task 0.2 — these are
 * typed directly off SPEC.md §9.2's entity field names (`Paper`,
 * `QueueDecision`, `SearchSession`) and §10.4's endpoint descriptions,
 * so the frontend and a real backend implementation are working off the
 * same field names rather than the frontend inventing its own.
 */

// ---------------------------------------------------------------------
// CONTRACTS.md §1 — Segmented-abstract response
// ---------------------------------------------------------------------

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

// ---------------------------------------------------------------------
// CONTRACTS.md §2 — API error shape
// ---------------------------------------------------------------------

/** Stable, machine-readable error codes pinned as of Tier 0 (CONTRACTS.md §2).
 * New codes are additive, not breaking — keep this list in sync with
 * CONTRACTS.md's table when a later task adds one. */
export type ApiErrorCode =
  | "service_unavailable"
  | "rate_limited"
  | "not_found"
  | "validation_error"
  | "zotero_not_connected"
  | "zotero_session_mismatch"
  | "internal_error"
  | (string & {});

export interface ApiErrorBody {
  code: ApiErrorCode;
  message: string;
}

export interface ApiErrorResponse {
  error: ApiErrorBody;
}

/** Thrown by the API client (api/client.ts) for every non-2xx response,
 * carrying the parsed `{code, message}` so callers can switch on `code`
 * (never on `message`, which is copy) per CONTRACTS.md §2. */
export class ApiError extends Error {
  readonly code: ApiErrorCode;
  readonly status: number;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
  }
}

// ---------------------------------------------------------------------
// CONTRACTS.md §3 — Zotero push per-item response shape
// ---------------------------------------------------------------------

export type ZoteroPushStatus = "success" | "failure";

export interface ZoteroPushResult {
  pmid: string;
  status: ZoteroPushStatus;
  zotero_item_key?: string;
  error?: ApiErrorBody;
}

export interface ZoteroPushResponse {
  collection_key: string;
  results: ZoteroPushResult[];
}

export interface ZoteroPushRequest {
  collection_key: string;
  pmids: string[];
}

// ---------------------------------------------------------------------
// Not yet pinned by CONTRACTS.md — typed off SPEC.md §9.2/§10.4 directly.
// ---------------------------------------------------------------------

/** SPEC.md §9.2 `Paper.authors` entry, from EFetch's AuthorList. */
export interface PaperAuthor {
  first_name: string;
  last_name: string;
}

/** The subset of `Paper` (§9.2) returned by `/search` and `/queue` —
 * title/metadata only, no abstract yet, per §7.1's two-stage fetch
 * strategy (§10.4's note on `GET /queue`). */
export interface QueuePaperSummary {
  pmid: string;
  title: string;
  authors: PaperAuthor[];
  last_author: string | null;
  journal: string | null;
  pub_date: string | null;
  doi: string | null;
  citation_count: number | null;
  /** §13.4: true when PubMed's PublicationType/correction-notice data
   *  marks this record as retracted or corrected — drives the "⚠
   *  Retracted" badge (owned by Task 2B). */
  retracted: boolean;
}

/** SPEC.md §9.2 `QueueDecision.decision`. */
export type DecisionValue = "pending" | "interested" | "not_interested";

/** SPEC.md §9.2 `QueueDecision.decided_via`. */
export type DecidedVia = "swipe" | "auto" | "manual_remove";

export interface QueueItem {
  paper: QueuePaperSummary;
  decision: DecisionValue;
  position: number;
}

export interface QueueResponse {
  items: QueueItem[];
  /** Present when more pages exist server-side (§10.4's transparent
   *  follow-up-ESearch-page behavior) — the frontend does not need to
   *  request "more" explicitly, but this lets a query hook know whether
   *  it has reached the end of the currently-known queue. */
  has_more: boolean;
}

/** SPEC.md §3.2.C / §9.2 `SearchSession.read_aloud_fields`. */
export type ReadAloudField = "last_author" | "journal" | "pub_date";

export type SortOrder = "relevance" | "recency" | "citations";

/** Body for `POST /api/v1/search` (§10.4). */
export interface SearchRequest {
  query: string;
  sort: SortOrder;
  read_aloud_fields: ReadAloudField[];
  default_swipe_behavior: "interested" | "not_interested";
  speed: number;
}

/** `GET /api/v1/search/settings` (§10.4) — pre-fill for Screen B (§3.5),
 * mirroring `SearchSession` (§9.2) minus its session/query-execution
 * fields. `null` when no search has ever been run this visit. */
export interface SearchSettingsResponse {
  query: string;
  sort: SortOrder;
  read_aloud_fields: ReadAloudField[];
  default_swipe_behavior: "interested" | "not_interested";
  speed: number;
}

/** Body for `PATCH /api/v1/decisions/{pmid}` (§10.4). */
export interface DecisionUpdateRequest {
  decision: DecisionValue;
  decided_via: DecidedVia;
}

/** `GET /api/v1/saved` (§10.4, §5.4) — `QueueDecision` rows where
 * `decision === "interested"`, joined with `Paper`. */
export interface SavedItem {
  paper: QueuePaperSummary;
  decided_at: string;
}

export interface SavedResponse {
  items: SavedItem[];
}

/** SPEC.md §8.4 — pyzotero-shaped collection, `GET /zotero/collections`. */
export interface ZoteroCollection {
  key: string;
  name: string;
}

export interface ZoteroCollectionsResponse {
  collections: ZoteroCollection[];
  /** Whether a `ZoteroConnection` exists for this session at all (§9.2) —
   * lets the frontend distinguish "connected, zero collections" from
   * "not connected yet" without relying solely on a 401-equivalent error,
   * for use once the collections panel has already loaded once. */
  connected: boolean;
}

export interface CreateZoteroCollectionRequest {
  name: string;
}

export interface CreateZoteroCollectionResponse {
  collection: ZoteroCollection;
}
