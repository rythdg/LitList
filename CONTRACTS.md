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
| `csrf_rejected` | 403 | A state-changing request (`POST`/`PUT`/`PATCH`/`DELETE`) either carried a disallowed `Origin` header or (for `POST`/`PUT`/`PATCH`) a non-`application/json` `Content-Type` (§10.7's CORS/CSRF guard). Rejected before the request body is parsed or any route handler/dependency runs. | 3D (`CSRFGuardMiddleware`) |

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

## 4. Simple success responses (no body)

A handful of state-changing endpoints have nothing meaningful to return on
success — e.g. `DELETE /api/v1/zotero/connection` (SPEC.md §9.6/§10.4's
"Disconnect Zotero" action, pinned by Task 3B after this gap was flagged
during Tier 2). These return **`204 No Content`, empty body**, rather than
`{}` or `{"success": true}` — one convention project-wide for "the action
happened, there's nothing to hand back." The frontend's shared `apiFetch`
(Task 2A, `frontend/src/api/client.ts`) already special-cases `204` to
resolve with `undefined` rather than attempting to parse a body, so this
was a confirming addition, not a new frontend capability.

Calling one of these endpoints when there is nothing to delete/act on
(e.g. `DELETE /zotero/connection` with no `ZoteroConnection` row present)
is **not** an error — still `204`, idempotently.

---

## 5. Queue/Saved/SearchSettings response shapes

`GET /api/v1/queue`, `POST /api/v1/search`, `GET /api/v1/saved`, and
`GET /api/v1/search/settings` (SPEC.md §10.4). Originally left unpinned
here ("internal to this backend/frontend pair, not shared with a third
integration") with only the `retracted: bool` field name called out —
that gap let Task 2B and Task 2C each independently invent a shape
*neither* of which matched what Task 3A actually shipped (nested
`{paper: {...}}` wrappers with a full `authors[]` array that the backend
never sends at this layer, a `decided_at` field the backend doesn't
return, a missing `total_count`). Found and fixed during Task 4A's
wiring pass; pinning the *real*, already-tested backend shape here now
so this doesn't happen again for whoever wires the remaining unpinned
shapes (e.g. `/zotero/collections`).

**These are flat objects — no nested `paper`/`author` sub-object, no
`authors[]` array.** `last_author` is a single pre-formatted display
string (PubMed ESummary's `LastAuthor` field, e.g. `"Chen W"`), not an
object — there is no full-author-list source available at this layer
(only `GET /papers/{pmid}/abstract`'s EFetch-backed response has that,
and it's out of scope for the queue/saved list views per §7.1's
two-stage fetch strategy).

### Shape

```ts
interface QueueItem {
  pmid: string;
  position: number;
  decision: "pending" | "interested" | "not_interested";
  title: string;
  last_author: string | null;
  journal: string | null;
  pub_date: string | null;
  doi: string | null;
  citation_count: number | null;
  /** SPEC.md §13.4's "⚠ Retracted" badge source, sourced from
   *  `Paper.retracted`. See caveat below. */
  retracted: boolean;
}

interface QueueResponse {
  items: QueueItem[];
  /** Total PubMed result count for the current query (§7.9's pagination
   *  bookkeeping) — not merely `items.length`. */
  total_count: number;
  has_more: boolean;
}

/** Same flat shape as `QueueItem` minus `decision` (always
 *  `"interested"` by construction — this endpoint only ever returns
 *  `interested` rows) — `position` is retained (the original queue
 *  position, not a saved-list-specific one). There is no `decided_at`
 *  field. */
interface SavedItem {
  pmid: string;
  title: string;
  last_author: string | null;
  journal: string | null;
  pub_date: string | null;
  doi: string | null;
  citation_count: number | null;
  position: number;
  retracted: boolean;
}

interface SavedListResponse {
  items: SavedItem[];
}

interface SearchSettingsResponse {
  /** `null` when no search has been run yet this visit (§3.5's pre-fill
   *  behavior) — not an empty string. */
  query: string | null;
  sort: "relevance" | "recency" | "citations";
  read_aloud_fields: ("last_author" | "journal" | "pub_date")[];
  default_swipe_behavior: "interested" | "not_interested";
  speed: number;
}
```

**Important caveat for `retracted` (both `QueueItem` and `SavedItem`):**
`retracted` can only be accurate once `GET /api/v1/papers/{pmid}/abstract`
has actually run EFetch for that PMID at least once (§7.1's two-stage
fetch strategy — `POST /search`'s own `QueueItem`s are built from
ESummary alone, which carries no `PublicationType` data). `retracted:
false` on a freshly-searched queue item therefore means "not known to be
retracted yet," not a confirmed guarantee — the same lazy-population
caveat SPEC.md §7.6 already describes for `citation_count`. The
frontend's "⚠ Retracted" badge (`StackScreen.tsx`/`SavedListPanel.tsx`)
should treat this the same way it already treats a citation count that
hasn't loaded yet: render nothing distinctive until the flag is
confirmed `true`, never render a false "not retracted" assurance.

---

## 6. Zotero OAuth callback redirect (query-param shape)

`GET /api/v1/zotero/auth/start` and `GET /api/v1/zotero/auth/callback`
(SPEC.md §8.2, §11.6). Both are hit by a **real browser navigation**
(the "Connect to Zotero" button is a full navigation, not a `fetch`;
Zotero itself redirects the user's browser to the callback URL) — so
every outcome, success or failure, must be a redirect back into the
frontend's one real URL-based route
(`frontend/src/routes/paths.ts`'s `ZOTERO_OAUTH_CALLBACK_PATH`,
`/oauth/zotero/callback`, Task 2A) rather than a JSON body, which the
browser would otherwise render as an unstyled dead end with no way back
into the app.

**This was a real, unpinned contract gap found during Task 4B's
wiring**, not a hypothetical: Task 2A's frontend built
`ZoteroCallbackRoute.tsx` against an assumed `?status=success` /
`?status=error&code=...&message=...` shape (flagged explicitly in its
own build-log COMPLETE entry as "confirm or correct against
CONTRACTS.md"), while Task 3B's original backend implementation
independently redirected to the SPA's home path with an unrelated
`?zotero=connected` param on success, and returned a raw
`{"error": {...}}` JSON body (no redirect at all) on failure — neither
side matched the other, and CONTRACTS.md didn't pin either. Fixed by
Task 4B: the backend now redirects to `settings.
zotero_post_auth_redirect_url` (the frontend's callback path) with the
query shape below in every case, matching what 2A had already built.

### Shape

```
GET {zotero_post_auth_redirect_url}?status=success
GET {zotero_post_auth_redirect_url}?status=error&code=<ApiErrorCode>&message=<url-encoded string>
```

- `status`: `"success"` | `"error"`. No other value is ever sent; the
  frontend treats anything else (e.g. a missing/malformed param, from
  someone hitting this URL directly) as `"unknown"` and shows a generic
  "still connecting" holding state (already built by Task 2A).
- `code`/`message`: present only when `status=error`; reuse this
  document's §2 `ApiErrorCode`/message fields verbatim rather than a
  one-off shape. Known values as of Task 4B: `zotero_session_mismatch`
  (403-equivalent — the OAuth request token didn't match the session
  that started the handshake, §10.2's binding primitive) and
  `service_unavailable` (Zotero's request-token or access-token step
  failed).
- On success, the backend has already set the rotated session cookie
  (§9.1) on the redirect response itself — the frontend never needs to
  make a follow-up call just to "confirm" the connection; the next real
  data fetch (e.g. `GET /zotero/collections`) will simply succeed.

Implemented in `backend/app/routes/zotero.py`'s `_callback_redirect`
helper; consumed by `frontend/src/routes/zoteroCallbackParams.ts`
(unchanged by this fix — its parsing already matched this shape, since
it's what 2A had assumed) and `ZoteroCallbackRoute.tsx`.

## Change log

- **2026-07-04 — Task 0.2 (initial):** all three shapes above pinned by
  `senior-fullstack-developer`. No prior version existed to diverge from.
- **2026-07-04 — Task 3B:** added §4 (simple 204 success-response
  convention) and pinned `DELETE /api/v1/zotero/connection` in SPEC.md
  §10.4 — the frontend's `useDisconnectZotero` hook already targeted this
  endpoint (SPEC.md §9.6's "Disconnect Zotero" action) but neither
  document listed it yet; implemented in `backend/app/routes/zotero.py`.
- **2026-07-04 — Task 3A (post-verification fix):** added §5, pinning
  `retracted: bool` on `QueueItem`/`SavedItem` — flagged by tester's
  TASK 3A VERIFY as a real functional gap (SPEC.md §13.4's badge was
  already built in the frontend against fixture data with no real
  backend field to consume). Implemented in `backend/app/routes/
  search.py`, `queue.py`, `saved.py`.
- **2026-07-04 — Task 3D:** added `csrf_rejected` (403) to §2's known
  `code` table — the new `CSRFGuardMiddleware`'s rejection response for
  a disallowed-origin or non-JSON-Content-Type state-changing request
  (SPEC.md §10.7). Implemented in `backend/app/middleware/security.py`,
  wired into `backend/app/main.py` alongside the rest of Task 3D's
  cross-cutting middleware stack (inbound rate limiting, the global
  exception-shape handler, baseline security headers).
- **2026-07-05 — Task 4A:** rewrote §5 from a single pinned field name
  into the full `QueueItem`/`QueueResponse`/`SavedItem`/
  `SavedListResponse`/`SearchSettingsResponse` shapes, matching the real
  (already-merged, 187-test-covered) backend response models exactly.
  This was a genuine drift fix, not a new decision: Task 2B's and Task
  2C's independently-invented frontend shapes for this "not yet pinned"
  gap disagreed with the real backend *and* with each other (nested
  `paper`/`authors[]` wrapper vs. flat object, a fabricated `decided_at`
  field, a missing `total_count`, a `publication_types[]`-based retracted
  check predating the already-shipped `retracted: bool` field). Fixed on
  the frontend only (`frontend/src/api/types.ts`,
  `frontend/src/components/screens/types.ts`, and every consumer) — no
  backend change was needed, since the backend was already correct.
- **2026-07-05 — Task 4B:** added §6, pinning the Zotero OAuth
  callback/start redirect's query-param shape — a genuine two-sided
  mismatch (see §6's own explanation), not a one-sided bug: Task 2A's
  frontend and Task 3B's backend each built a different, unpinned
  assumption for this exact redirect. Fixed on the backend
  (`backend/app/routes/zotero.py`'s new `_callback_redirect` helper,
  `backend/app/config.py`'s `zotero_post_auth_redirect_url` default) to
  match what the frontend (`zoteroCallbackParams.ts`,
  `ZoteroCallbackRoute.tsx`) already expected — no frontend change was
  needed for the redirect shape itself, since 2A's assumption turned out
  to be the more spec-aligned of the two (§8.2 step 6's "bounces the
  browser to the fixed in-app post-auth path").
