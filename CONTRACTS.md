# LitList — Shared Data Contracts

This document pins the exact JSON shapes that cross the backend/frontend
seam, per `BuildPlan.md` Task 0.2. It exists so that tasks built in
parallel later (1D/2D for the segmented-abstract shape; 3A/3B/3D and
2C/4A/4C for the error shape; 1C/3B and 2B/4B for the Zotero push shape)
build against the *same* shape from day one instead of each guessing —
and reconciling later.

**Rule for the whole project (see `BuildPlan.md`'s standing procedure):**
if implementation reveals this document is wrong or incomplete, the fix
is to update this file *and* every consumer in the same piece of work,
and to log the change (what/why) in the changing agent's build log — never
to quietly patch one side to tolerate a mismatch instead.

These are types/field names + one example JSON per shape — not an
implementation. Backend types are conceptually Pydantic/SQLModel models;
frontend types are the matching TypeScript interfaces both sides derive
from this document independently (no shared codegen in v1).

---

## 1. Segmented-abstract response

`GET /api/v1/papers/{pmid}/abstract` (SPEC.md §10.4, §6.5, §6.4, §7.5,
§13.3).

Built once by the backend tokenizer (Task 1D, `backend/app/text/
tokenize.py`) and consumed, never recomputed, by the frontend playback
engine (Task 2D, `frontend/src/playback/usePlaybackEngine.ts`) — see
`BuildPlan.md`'s note under Task 2D on why this logic lives in exactly
one place.

### Shape

```ts
type PauseClass = "structural" | "sentence";
// "structural": the long (~800ms-1s) gap used for genuine section breaks
//   (title -> metadata -> abstract start; before each section header) — §6.4.
// "sentence": the short (~150-350ms) gap between consecutive sentences
//   within the same section/passage — §6.4.

type SegmentKind = "section_header" | "sentence";
// "section_header": a structured-abstract label (BACKGROUND, METHODS,
//   RESULTS, CONCLUSIONS, ...) spoken as its own short utterance before
//   its section, per §7.5. Present only when PubMed's AbstractText Label
//   attribute exists for this abstract; abstracts with no structured
//   labels contain zero segments of this kind.
// "sentence": one sentence of abstract body text.

interface AbstractSegment {
  /** 0-based order matching TTS queue order. This is the sync signal
   *  §6.5 describes: "the currently-playing utterance's index tells the
   *  UI exactly which sentence to highlight" — the frontend keys its
   *  highlight state off this field, never off `onboundary` events
   *  (those are bonus-only, per §6.5). */
  index: number;

  kind: SegmentKind;

  /** The structured-abstract section this segment belongs to (e.g.
   *  "BACKGROUND"), denormalized onto every segment (not just headers)
   *  so the frontend never has to walk backward to find "which section
   *  is this sentence in." `null` for unstructured abstracts. */
  section_label: string | null;

  /** Exactly what's shown on screen for this segment — sourced from
   *  `Paper.display_abstract` (§9.2), untouched by TTS normalization.
   *  The frontend renders this as a framework element (e.g. a React
   *  <span>), never via HTML-string interpolation — see the XSS note
   *  in §6.5/§11.3; this field is untrusted external (PubMed) text. */
  display_text: string;

  /** What's actually queued as the `SpeechSynthesisUtterance` for this
   *  segment — sourced from `Paper.spoken_abstract` (§6.3's
   *  normalization pipeline: abbreviation expansion, number-reading,
   *  etc.). Never shown on screen. */
  spoken_text: string;

  /** Display char range of `display_text` within the paper's full
   *  `display_abstract` string — SPEC.md §6.5's `displayCharRange`.
   *  0-indexed, end-exclusive (`display_abstract[char_start:char_end]
   *  === display_text`). Not meaningful for `section_header` segments
   *  against body text; still populated against the header's own
   *  position in `display_abstract` for consistency. */
  char_start: number;
  char_end: number;

  /** The pause to insert *before* this segment's utterance is queued
   *  (§6.4's two-tier pause logic). The very first segment is always
   *  "structural" (it follows the title/metadata utterances, which this
   *  endpoint does not itself return — those come from the queue/search
   *  response the frontend already has). */
  pause_class: PauseClass;
}

interface SegmentedAbstractResponse {
  pmid: string;

  /** §13.3: true when this record's PubMed `Language` field doesn't
   *  match the active narration voice's locale. The frontend must skip
   *  audio narration entirely for this paper (still show `segments[].
   *  display_text` on screen) and surface the "Narration unavailable
   *  for this language" note — the backend makes this call once, using
   *  1B's captured `Language` field, so the frontend never guesses. */
  narration_unavailable: boolean;

  segments: AbstractSegment[];
}
```

### Example

```json
{
  "pmid": "38279812",
  "narration_unavailable": false,
  "segments": [
    {
      "index": 0,
      "kind": "section_header",
      "section_label": "BACKGROUND",
      "display_text": "Background",
      "spoken_text": "Background.",
      "char_start": 0,
      "char_end": 10,
      "pause_class": "structural"
    },
    {
      "index": 1,
      "kind": "sentence",
      "section_label": "BACKGROUND",
      "display_text": "Prior work has shown mixed results in Fig. 2, e.g. reduced uptake vs. controls.",
      "spoken_text": "Prior work has shown mixed results in figure two, for example reduced uptake versus controls.",
      "char_start": 12,
      "char_end": 91,
      "pause_class": "sentence"
    },
    {
      "index": 2,
      "kind": "section_header",
      "section_label": "METHODS",
      "display_text": "Methods",
      "spoken_text": "Methods.",
      "char_start": 94,
      "char_end": 101,
      "pause_class": "structural"
    },
    {
      "index": 3,
      "kind": "sentence",
      "section_label": "METHODS",
      "display_text": "We enrolled 40 participants across two sites.",
      "spoken_text": "We enrolled forty participants across two sites.",
      "char_start": 103,
      "char_end": 148,
      "pause_class": "sentence"
    }
  ]
}
```

---

## 2. API error shape

Every non-2xx JSON response from `/api/v1/...`, project-wide (SPEC.md
§10.3). One shape, one frontend error-rendering code path (Task 4C) keyed
off `code` — never a per-endpoint ad hoc error body, and `message` is
always a safe, pre-written string (never raw exception text or a stack
trace — full details are logged server-side only, per §10.3/§12.6).

### Shape

```ts
interface ApiError {
  error: {
    /** Stable, machine-readable identifier. The frontend's shared error
     *  component (Task 4C) switches on this, not on `message` (which is
     *  copy and may be reworded without breaking the frontend). */
    code: string;
    /** Safe, human-readable, pre-written per `code`. Never interpolates
     *  raw exception text, file paths, or query fragments. */
    message: string;
  };
}
```

### Known `code` values pinned as of Tier 0

This list grows as later tasks need new codes — adding one is not a
breaking change to this shape, only an addition to this table. Any task
introducing a new code should add it here in the same piece of work.

| `code` | HTTP status | Meaning | First needed by |
|---|---|---|---|
| `service_unavailable` | 503 | An external dependency (PubMed, iCite, or Zotero) is unreachable/down — distinct from the caller being rate-limited or from the caller being offline (§13.6). Already-cached `Paper` rows still serve normally; this code only applies to the parts of a request that genuinely need a live external call. | 3A (`/search`, `/queue`), 3B (Zotero routes) |
| `rate_limited` | 429 | The caller (session/IP) has exceeded LitList's own inbound rate limit (§10.5) — distinct from `service_unavailable`, which is about an *external* provider, not the caller's own request volume. | 3D (inbound middleware) |
| `not_found` | 404 | Referenced resource (PMID, decision, collection) doesn't exist for this session. | 3A, 3B |
| `validation_error` | 400 | Request body/query failed validation (e.g. malformed search body). | 3A, 3B, 3C |
| `zotero_not_connected` | 401 | No `ZoteroConnection` exists yet for this session — the frontend uses this to trigger the "Connect to Zotero" step (§5.5), per §10.4's note on `/zotero/collections`. | 3B |
| `zotero_session_mismatch` | 403 | OAuth callback's request token doesn't match the session that started the handshake (§10.2's binding primitive, §9.6). | 3B |
| `internal_error` | 500 | Unhandled server error; the exception-shape guarantee (never leak internals) applies here most of all. | 3D (catch-all handler) |

### Example

```json
{
  "error": {
    "code": "service_unavailable",
    "message": "PubMed is currently unavailable. Please try again shortly."
  }
}
```

---

## 3. Zotero push per-item response shape

`POST /api/v1/zotero/push` (SPEC.md §10.4, §8.6, §8.7). A multi-batch
push can partially succeed (batch 1 of 50 saves, batch 2 fails), so this
is **always a per-PMID list, never an all-or-nothing result** — the
backend tracks exactly which papers still need saving via `ZoteroExport`
rows (§9.2), and the frontend's retry / CSV-fallback flow (§4.4/§5.5)
only needs to cover what's actually missing.

### Shape

```ts
type ZoteroPushStatus = "success" | "failure";

interface ZoteroPushResult {
  pmid: string;
  status: ZoteroPushStatus;
  /** Present only when status === "success" — the Zotero-assigned item
   *  key (§9.2's `ZoteroExport.zotero_item_key`), useful for debugging/
   *  future updates even though v1 never edits existing items. */
  zotero_item_key?: string;
  /** Present only when status === "failure" — reuses the pinned error
   *  shape's inner object (not the full `{"error": {...}}` envelope,
   *  since this is one item's failure within an otherwise-200 response,
   *  not the request itself failing). */
  error?: {
    code: string;
    message: string;
  };
}

interface ZoteroPushResponse {
  collection_key: string;
  results: ZoteroPushResult[];
}
```

### Example

```json
{
  "collection_key": "ABCD1234",
  "results": [
    { "pmid": "38279812", "status": "success", "zotero_item_key": "XJ2K9F3P" },
    {
      "pmid": "38279813",
      "status": "failure",
      "error": {
        "code": "service_unavailable",
        "message": "Zotero is currently unavailable. Please try again shortly."
      }
    }
  ]
}
```

---

## Change log

- **2026-07-04 — Task 0.2 (initial):** all three shapes above pinned by
  `senior-fullstack-developer`. No prior version existed to diverge from.
