# LitList — Build Plan

This document sequences the implementation of `SPEC.md` into **tiers**,
ordered by actual dependency (what must exist before what), not by the
spec's narrative section order. Every task cites the `SPEC.md` section(s)
it implements and the `SPEC.md` §15 test(s) that gate it.

*Revised once after an adversarial review surfaced several false claims
of parallel-independence and process gaps in the first draft — see the
"What changed" note at the end. This version is the one to build from.*

**How to read this document:** a tier can contain multiple **waves**.
Within one wave, every listed task is genuinely independent of every
other task in that wave — verified, not just asserted — so they are
built **and tested concurrently by separate subagents**, each in its own
git worktree. A later wave in the same tier may depend on the earlier
wave in that tier having merged first. A tier is not "done" until every
task in every wave has its own tests green; the next tier does not start
until the current one is fully green.

## Execution & merge protocol (applies to every wave below)

- **Dispatch together, or it isn't parallel.** All of a wave's `Agent`
  calls (with `isolation: "worktree"`) must be issued in a single
  message. Launching them one at a time defeats the entire point of this
  plan's tier structure — say so explicitly here since it's easy to
  execute this document tier-by-tier without actually parallelizing
  within one.
- **The orchestrating session owns merges, not the subagents.** After a
  wave's subagents report back, the orchestrator (a) checks each diff
  against `CONTRACTS.md` for shape conformance — a light check, not a
  full review — (b) merges branches into the shared integration branch
  one at a time, resolving any conflict itself, and (c) only then
  declares the wave's exit gate met. The orchestrator does **not** also
  run a full adversarial pass itself — that duplicates
  `adversarial-generalist`'s actual job, doubles the orchestrator's load
  for no benefit, and risks the two reviews silently disagreeing with
  no one noticing. One thorough adversarial review per task, from the
  role built for it, beats two partial ones.
- **A merge requires proof, not a specialist's word.** The orchestrator
  may never merge on a specialist's own `COMPLETE` log entry alone.
  Before merging task *T*, the orchestrator confirms — by actually
  checking the logs, not by recalling a subagent's summary — that
  `logs/tester.build.log` contains a `TASK T VERIFY` entry and
  `logs/adversarial-generalist.build.log` contains a `REVIEW: T` entry,
  both for that exact task ID. No entry, no merge — go dispatch the
  missing check instead of proceeding on trust.
- **Blocking findings are a veto, not a vote — this is asymmetric by
  design.** If `adversarial-generalist` logs a `blocking` finding on a
  task `tester` already marked as gate-met, the finding wins regardless
  of order or of `tester`'s verdict; `tester` cannot rule an adversarial
  finding out of scope. `significant`/`minor` findings do not auto-block,
  but the orchestrator must log its own decision (which way it went and
  why) rather than silently picking a side — see "Escalation & conflict
  resolution" below for what happens if the orchestrator can't resolve
  it from the artifacts alone.
- **Partial-wave failure does not get merged around.** If 3 of 4 tasks in
  a wave pass and one doesn't, the three passing branches stay
  unmerged-but-ready; the wave's gate is not met and the next
  tier/wave does not start until the failing task is fixed (by a
  follow-up agent) and merged too. Do not cherry-pick a "good enough"
  partial merge to keep moving — later tiers assume the whole wave landed.

**Open input:** you mentioned a Claude Design prototype directory you'll
share once ready. It slots into **Tier 2, Task 2B** — once shared, that
task becomes "adapt the Claude Design components into the app's
component structure" rather than building from the ASCII wireframes.
Nothing else in this plan depends on that hand-off.

---

## Inter-agent communication & handover protocol

This section exists because "parallel subagents" and "clean handover"
don't happen automatically — they require an explicit protocol, the same
way the tier structure itself required an explicit protocol before the
adversarial review caught the gaps in the first draft.

### The orchestrator keeps its own log too — it is not exempt

Every other role has a `logs/<agent-name>.build.log`; the orchestrator
keeps `logs/orchestrator.log` on the same append-only discipline, because
it is a department too and it is the one department with no one checking
its work by default. It logs: every merge decision (task ID, which gate
entries it verified per the point above), every escalation it raised or
resolved (see below), and every `significant`/`minor`-finding call it
made and why. This exists specifically so a replacement or resumed
orchestrator session — or the human, auditing after the fact — has
continuity instead of having to reconstruct "why was this merged" from
five other people's logs and git history.

Separately, the orchestrator posts a short **rollup entry to
`logs/status.log`** at the close of every wave — one line per task
(done / blocked / gate-not-met) plus anything currently open — so the
human has one place to check "are we on track" without reading all five
per-agent logs end to end. The per-agent logs remain the detailed record
for when the human wants to go deeper; `status.log` is the summary layer
that was previously missing.

### Escalation & conflict resolution

Not every disagreement can be resolved by re-reading a diff. When the
orchestrator cannot resolve a conflict from the artifacts alone —
`tester` and `adversarial-generalist` disagree in a way severity
precedence doesn't settle, a specialist disputes a finding and the
orchestrator can't tell who's right, or a task is blocked on something
outside any agent's tools (an external account, a real decision only the
human can make) — the rule is: **two round-trips without resolution
escalates to the human**, logged in `logs/orchestrator.log` as an
explicit escalation with the competing positions stated plainly. This
replaces the previous default of "everything silently falls on the
orchestrator" with a defined trigger, so the human is pulled in
deliberately rather than either never or by accident.

### `CONTRACTS.md` changes after Tier 0 are a standing procedure, not a one-off

The original plan treated a post-hoc contract fix (Task 4A's worked
example) as an ad hoc "process bug." It's a real, recurring case and
gets a real procedure: any change to `CONTRACTS.md` after Tier 0 requires
the orchestrator to (1) log the change and its reason in
`logs/orchestrator.log`, (2) grep every agent's build.log for citations
of the shape that changed to find every already-merged task that
consumed the old version, and (3) dispatch one scoped fix task per
affected consumer before the current tier's exit gate can close — a
contract change is never considered "done" just because the task that
prompted it is done.

### A `user` finding only counts once it's in the durable system

`user` reports conversationally to the human and keeps no build.log by
design (see `user.md`) — which means a real finding ("swipe doesn't work
on a trackpad") can otherwise live only in a conversation and never
reach the specialist who'd fix it. Rule: once the human decides a `user`
finding is actionable, the orchestrator logs it as a new task entry in
the owning specialist's build.log (a `START` entry citing "user-reported"
as the source) before dispatching the fix — this is what brings it into
the same handover system everything else already uses, rather than
letting it stay word-of-mouth.

### The human can interrupt a wave without breaking the barrier model

Waves are a hard barrier by design (below), which is good for
consistency but shouldn't mean the human has no way to redirect capacity
once a wave is already dispatched. If the human asks to cancel or
deprioritize one in-flight task mid-wave, the orchestrator logs the
request, and the wave's gate still does not close until that task is
either completed normally or explicitly descoped from the tier **by the
human, in writing, logged** — never silently dropped just because the
human lost interest in a status update.

### There is no agent-to-agent channel — everything routes through the orchestrator and shared files

A subagent (other than a `fork`, which isn't used in this build) starts
with **zero memory of anything** — not this conversation, not another
agent's in-flight work, not even its own prior invocation unless the
orchestrator explicitly resumes it. Agents cannot message each other
directly. Every handover between two pieces of work happens through one
of three durable, shared artifacts, and only through them:

1. **`SPEC.md` / `BuildPlan.md` / `CONTRACTS.md`** — what to build and
   the shape it must take. Static, changes rarely, read before starting.
2. **The merged code on the integration branch** — what actually exists,
   ground truth for anything already merged.
3. **`logs/<agent-name>.build.log`** — what happened and *why*, including
   the things the code alone doesn't show: a pivot away from the
   originally-planned approach, a contract that turned out to be wrong,
   a corner deliberately cut and why, a blocker that got worked around.
   This is the piece the first draft of this plan was missing, and it's
   exactly what makes a handover "smooth" instead of the next agent
   re-discovering the same wrinkle from scratch.

The orchestrator (this session, directed by the human) is the sole
coordinator: it decides what to dispatch, dispatches it, collects
results, runs the validation-checkpoint pattern, and merges. Agents never
wait on each other directly — they wait on the orchestrator to give them
a task, and the orchestrator is the one that waits on tier/wave gates
(see below).

### Every agent reads every relevant log before starting, not just BuildPlan.md's description

All five build-pipeline agents already have unrestricted `Read` access —
this is now an explicit *requirement*, not just a capability: **before
starting any task, an agent must read**:

1. Its own task's entry in `BuildPlan.md` and the `SPEC.md` section(s) it
   cites.
2. `CONTRACTS.md` for any shape the task produces or consumes.
3. **The tail of `logs/<agent-name>.build.log` for every task listed
   under its own task's "Depends on"** — e.g. before starting 1C, read
   `senior-backend-developer.build.log`'s 1A entries; before starting
   3A, read the same log's 1A/1B/1D entries; before starting 4A, read
   both `senior-backend-developer.build.log` (3A) and
   `senior-frontend-developer.build.log` (2C/2D).

Any agent may read any other agent's log at any time — logs are not
private to their author. A dependency's **PIVOT** entries are the most
important thing to check here: they capture exactly the kind of
real-world wrinkle (a contract that had to change, an assumption that
didn't hold) that `BuildPlan.md`'s static task description was written
before anyone hit. Treat a dependency's log as more authoritative about
what actually happened than `BuildPlan.md`'s description of what was
*supposed* to happen — if they conflict, the log wins, and that conflict
is itself worth a line in your own START entry.

**The orchestrator enumerates the exact dependency chain in the dispatch
prompt — it is not the dispatched agent's job to reconstruct it.** A
task with several indirect dependencies (e.g. 4A transitively depends on
0.2, 1A, 1B, 1D, 2C, 2D, 3A) has no single place listing that full chain
other than by tracing `BuildPlan.md`'s prose by hand, which is exactly
the kind of thing a fresh agent with no memory shouldn't be asked to
redo on its own every launch. Every dispatch prompt states, explicitly
and by task ID, which log files and which entries to read before
starting — the agent still does the reading, but the orchestrator does
the tracing.

### When the orchestrator spins a new agent vs. resumes one

- **Default: one task = one fresh subagent**, briefed with everything it
  needs in the prompt (per the point above, since it has no memory).
  This is the normal case for every task in every tier.
- **Exception, still within the same unmerged task**: if `tester` or
  `adversarial-generalist` finds an issue in work that hasn't been merged
  yet, the orchestrator's default is to resume the same specialist agent
  (via `SendMessage` to its agent id, if still live in this session)
  with the specific finding, rather than spinning a brand-new agent and
  re-explaining the whole task from scratch. This is a same-task fix
  loop, not a new task.
- **Once a task has merged, a later fix is a new task**, briefed fresh —
  point the new agent at the specific finding (verbatim from `tester`/
  `adversarial-generalist`) and the relevant `build.log` entries, never
  send it in to "figure out what's wrong" unaided.
- **A follow-up agent's prompt must always include the actual finding
  text**, not a paraphrase — the same verbatim-reporting discipline
  `tester` and `adversarial-generalist` already follow when reporting
  applies symmetrically to how the orchestrator hands findings onward.

### What runs in parallel, and how the orchestrator decides

For any wave in the tier list above, the orchestrator: (1) confirms every
task in the wave has its declared dependencies already merged (check the
tier's own "Depends on" language and the relevant build.logs — not just
assumption), (2) dispatches every task in that wave's `Agent` calls in a
**single message** so they actually run concurrently, (3) treats the
wave as a barrier — waits for every dispatched agent to report back
before evaluating the wave's exit gate, never evaluating tasks
one-by-one as they trickle in, and (4) only then runs the
validation-checkpoint pattern per task and merges.

**If two "parallel" tasks in a wave turn out to need to coordinate with
each other mid-flight, that is a signal the wave was mis-scoped** — the
same false-independence failure mode the adversarial review already
caught once in the first draft (1A/1C, 3A-3D). The fix is to stop, split
the wave correctly (as was done for Tier 1 and Tier 3), and re-dispatch
— not to try to route a live message between two in-flight agents, which
this architecture doesn't support anyway.

### When and how the orchestrator waits

- **Within a wave**: waits for all dispatched agents to report back
  (a hard barrier) before declaring anything about that wave.
- **Across tiers**: Tier *N+1* is not dispatched until Tier *N*'s exit
  gate is confirmed met — `tester` and `adversarial-generalist` have both
  signed off (per their logs) and the orchestrator has actually merged.
  The two stated exceptions remain as designed: **Tier 2** (frontend
  foundation) starts alongside Tier 1 since it depends only on Tier 0's
  contracts, and **Tier 5** (deployment infra) starts alongside Tier 1-4
  since it depends only on Tier 0's `db.py` module — both are explicit,
  named exceptions to the general wait-for-the-prior-tier rule, not
  license to skip waiting elsewhere.
- **On a partial-wave failure**: the orchestrator waits on the specific
  failing task's fix-and-remerge before declaring the wave's gate met,
  per the partial-failure rule above — the passing tasks' branches wait
  too, even though they're individually done.

---

## Dependency graph (tier-level)

```
Tier 0  Foundation + shared contracts (sequential)
   │
   ├──────────────┬──────────────┐
   ▼              ▼              ▼
Tier 1        Tier 2         Tier 5
Backend       Frontend       Deployment
core modules  foundation     & CI infra
(2 waves)     (parallel)     (parallel,
   │              │           starts early)
   ▼              │
Tier 3            │
Backend API       │
surface           │
(2 waves)         │
   │              │
   └──────┬───────┘
          ▼
       Tier 4
   Frontend↔Backend
     integration
      (parallel)
          │
          ▼
       Tier 6
   Full-system test
   pass (parallel)
```

Tier 5 has no dependency on Tiers 1-4's *feature* code, only on Tier 0's
DB-connection contract (see Task 0.1), so it can be provisioned as early
as Tier 0 finishes.

---

## Tier 0 — Foundation & shared contracts (sequential, one agent)

The first draft of this plan under-scoped Tier 0 to just scaffolding,
which let real cross-task dependencies (a shared data shape, a shared
fixture corpus, a shared DB-connection module) slide silently into later
"parallel" tiers, where they caused exactly the false-independence
problem the tier structure exists to avoid. All three are pinned down
here instead.

**Task 0.1 — Repo, tooling, and DB-connection scaffolding**
- Monorepo layout: `backend/` (FastAPI + SQLModel, §10.1) and `frontend/`
  (React + TS + Vite, §11.1).
- Backend: FastAPI app skeleton, Uvicorn entrypoint, `ruff`/`mypy`,
  `pytest` config; **a minimal `backend/app/db.py` engine module** (env
  var-driven connection string, `sqlalchemy-libsql` driver wired in but
  pointed at local SQLite for dev) — this exists specifically so Tier 1's
  data model (1A) and Tier 5's infra check (5A) build on the *same*
  connection module instead of each inventing one that the other later
  has to reconcile.
- Frontend: Vite + React + TS + Tailwind scaffold, ESLint/`tsc`, Vitest.
- Empty GitHub Actions workflow files (filled in by Tier 5, Task 5B).
- **Test gate:** both apps boot (`/health`, empty Vite shell); `db.py`
  connects to local SQLite and Turso-via-env-var interchangeably (a
  one-line manual check, not a full test suite yet).

**Task 0.2 — Shared data contracts**
Written down once, here, so no two tasks in later "parallel" tiers can
each guess a different shape for the same thing:
- **Segmented-abstract shape** — the exact JSON returned by
  `GET /papers/{pmid}/abstract` (§10.4) and consumed by the playback
  engine (§6.5, §11.3): field names for sentence text, display char
  range, and section label (§7.5's structured-abstract headers). 1D
  (backend tokenizer) and 2D (frontend playback engine) both build
  against this from day one instead of "porting logic" between them
  later — see the note under Task 2D on why the tokenizer must not exist
  twice.
- **API error shape** (`{"error": {"code", "message"}}`, §10.3) and the
  **Zotero push per-item response shape** (§8.7) — both consumed by
  multiple later tasks (3A/3B/3D and 2C/4A/4C) and must be fixed now.
- Lands as a short `CONTRACTS.md` or shared TypeScript/Pydantic type
  stub, not full implementation.

**Task 0.3 — Shared test fixture corpus**
- The abbreviation-heavy sentence corpus (`Fig. 2`, `vs.`, `et al.`, `e.g.`
  — §6.5, §15.1, §15.9) used by **both** 1D's backend tokenizer tests and
  2D's frontend playback-engine tests — written once so backend and
  frontend aren't independently guessing at edge cases and silently
  covering different ones.
- 2-3 sample raw PubMed ESummary/EFetch payloads and a sample Zotero
  collections/item-creation response, used by 1B/1C's mocked tests and
  later by 2C's MSW mocks — same reasoning.

**Tier 0 exit gate:** scaffolding boots; `CONTRACTS.md` and the fixture
corpus exist and are committed; every later task references them instead
of inventing their own.

---

## Tier 1 — Backend core modules (2 waves)

**Wave 1 (solo): Task 1A — Data model & session identity** (§9 all,
§10.2)
This is deliberately *not* parallelized with 1C anymore — the first
draft claimed it could be, but 1C's OAuth handshake directly imports 1A's
session-binding primitive, which is a same-tier hard dependency, not a
"exercised later" formality. Building 1A alone first, and merging it,
before 1C starts is what actually makes 1C's later claim of independence
true.
- SQLModel entities on top of Task 0.1's `db.py`: `Session`,
  `ZoteroConnection`, `SearchSession`, `Paper`, `QueueDecision`,
  `ZoteroExport` (§9.2).
- CSPRNG `session_id` generation + rotation-on-Zotero-connect (§9.1).
- Fernet encryption for `oauth_token`/`oauth_token_secret`, keyed by a
  placeholder local-dev `TOKEN_ENCRYPTION_KEY` (§9.6).
- Session-identity FastAPI middleware, cookie issuance (§10.2),
  **including the request-token-to-session binding primitive** that 1C
  will import (§10.2's OAuth addendum).
- **Owns:** `backend/app/models/`, `backend/app/middleware/session.py`.
- **Tests (§15.1):** CSPRNG source + rotation-on-escalation; Fernet
  round-trip with independent-secret assertion; binding primitive rejects
  a mismatched/expired token.
- **Exit:** merged to the integration branch before Wave 2 starts.

**Wave 2 (parallel — 3 subagents, depends on Wave 1 merged): Tasks 1B,
1C, 1D**

**1B — PubMed client** (§7 all)
- `pubmed_client`: ESearch, batched ESummary, EFetch (§7.2-7.5) against
  Task 0.3's fixture payloads via `respx` — no real network calls.
- Outbound pacing (§7.7), backoff on rate-limit response.
- iCite client (§7.6) with graceful sort-degradation if unreachable.
- Zero-result/malformed-record handling (§7.9).
- **Extraction for §13.4:** capture `PublicationType` (retracted/errata
  flag) and the record's `Language` field from EFetch — needed by 1D's
  language-mismatch check and 2B's retracted badge; cheap to grab here
  since EFetch already returns them.
- **Owns:** `backend/app/integrations/pubmed.py`, `icite.py`.
- **Tests (§15.1, §15.8 outbound half):** fake-clock pacing; mocked
  429/`Retry-After` backoff; zero-result path; iCite-unreachable
  degradation.

**1C — Zotero client & OAuth handshake** (§8 all, route handlers are 3B)
- OAuth 1.0a handshake using **Wave 1's merged** session-binding
  primitive (§10.2 addendum) and a fixed, non-dynamic callback redirect
  (§8.2).
- `pyzotero`-based client: collections list/create (§8.4/8.5), batched
  item push with per-item success/failure per Task 0.2's pinned shape
  (§8.6/8.7).
- **Owns:** `backend/app/integrations/zotero.py`,
  `backend/app/auth/oauth.py`.
- **Tests (§15.1, §15.7 automated half):** binding enforced;
  mismatched/expired token rejected; fixed callback redirect; mocked
  partial-batch push reports correct per-item status.

**1D — Text normalization & sentence tokenizer** (§6.3, §6.4's pause
logic, §6.5's tokenizer, §13.3's language check)
- Normalization pipeline (§6.3) producing `spoken_abstract`.
- Abbreviation-aware tokenizer producing Task 0.2's pinned
  segmented-abstract shape for both `display_abstract` and
  `spoken_abstract` — **this is the only place this logic lives**;
  nothing in Tier 2 re-implements it (see 2D).
- Structural-vs-sentence pause-class assignment (§6.4), also emitted in
  the pinned shape so the frontend only ever *renders* timing decisions,
  never computes them.
- **§13.3 language-mismatch flag:** using 1B's captured `Language` field,
  mark a paper `narration_unavailable: true` in the segmented-abstract
  response when it doesn't match the active narration locale, rather
  than making the frontend guess.
- **Owns:** `backend/app/text/normalize.py`, `backend/app/text/tokenize.py`.
- **Tests (§15.1, §15.9 tokenizer half):** Task 0.3's golden-file corpus
  — no mid-sentence splits; normalization unit tests per construct;
  language-mismatch flag set correctly.

**Tier 1 exit gate:** Wave 1 merged, then Wave 2's three modules
independently green and merged.

---

## Tier 2 — Frontend foundation (parallel — 4 subagents, runs concurrently with Tier 1)

These need Tier 0 (scaffolding + the pinned contracts) but nothing from
Tier 1's *implementation* — only the *shape* Task 0.2 already fixed —
which is what makes running this tier alongside Tier 1 legitimate rather
than merely convenient.

**2A — App shell, PWA, routing** (§11.1, §11.5, §11.6)
- `vite-plugin-pwa` manifest + service worker precache.
- The Zotero OAuth callback route (§11.6) — the one real route needed.
- **Owns:** `frontend/src/main.tsx`, `vite.config.ts`, `src/routes/`.
- **Tests (§15.5):** Lighthouse CI installability check.

**2B — UI screens from wireframes / Claude Design prototype** (§5 all,
§13.4's retracted badge)
- Presentational components for every screen (5.1-5.5), driven by
  mock/fixture data — no TanStack Query, no real backend.
- Tap/keyboard decision buttons (§13.1), Disconnect Zotero (§9.6/§5.4),
  and a "⚠ Retracted" badge (§13.4) when a paper's fixture data carries
  that flag.
- **Once the Claude Design directory is shared:** port those components
  in here; the wireframes remain the spec of record for *behavior*.
- **Owns:** `frontend/src/components/screens/`.
- **Tests (§15.2):** per-screen-state rendering (idle, loading, empty-
  result §5.3a, error §5.5 3b); safe-array text rendering regression test
  (no raw HTML interpolation of title/abstract).

**2C — State architecture scaffolding** (§11.2)
- Zustand stores per §11.2's local-only list.
- TanStack Query client + typed hooks for every §10.4 endpoint, using
  Task 0.2's pinned error/response shapes against MSW mocks seeded from
  Task 0.3's fixture payloads (not invented ad hoc).
- **Owns:** `frontend/src/state/`, `frontend/src/api/`.
- **Tests (§15.2):** store transitions in isolation.

**2D — Playback engine module** (§6 all except tokenizer, §11.3, §13.2,
§13.7)
- `usePlaybackEngine`: per-sentence `SpeechSynthesisUtterance` queuing,
  mute-via-`volume=0`, timer-based fallback (§6.2/§6.5/§13.7), `onboundary`
  as bonus-only precision.
- **Consumes, does not compute, segmentation and pause timing** — reads
  Task 0.2's pinned shape (sentence text/range/pause-class), populated by
  1D. This resolves the first draft's unresolved hedge ("ported… or
  consumed") in favor of a single decision: tokenizer/pause logic lives
  in exactly one place (1D, backend) to prevent drift between two
  implementations of the same rule.
- Screen Wake Lock API while narration plays (§13.2's partial mitigation)
  and the one-time "audio narration isn't available in this browser"
  notice (§13.7) when `speechSynthesis` is absent entirely.
- Built and tested against Task 0.3's fixture segmented abstracts.
- **Owns:** `frontend/src/playback/usePlaybackEngine.ts`.
- **Tests (§15.9):** timer-fallback actually exercised; mute advances
  highlight on the same clock; speed scales audio + highlight together;
  mid-narration cancellation has no overlap; Wake Lock requested on play.

**Tier 2 exit gate:** all four modules' tests green against
fixtures/mocks — not yet proof the real backend integrates cleanly,
which is Tier 4's job.

---

## Tier 3 — Backend API surface (2 waves, depends on all of Tier 1 merged)

**Wave 1 (parallel — 3 subagents): Tasks 3A, 3B, 3C**

**3A — Core loop endpoints** (§10.4 search/queue/abstract/decisions/saved)
- `POST /search`, `GET /search/settings`, `GET /queue`,
  `GET /papers/{pmid}/abstract` (returns Task 0.2's pinned shape),
  `PATCH /decisions/{pmid}`, `GET /saved`, `DELETE /saved/{pmid}`.
- Transparent pagination follow-up (§7.9).
- **§13.6 external-dependency-downtime handling:** when 1B's PubMed/iCite
  wrapper signals "unreachable" (distinct from a rate-limit backoff),
  `/search` and `/queue` return a specific `service_unavailable` error
  code (Task 0.2's error shape) rather than a generic 500 — already-
  cached `Paper` rows keep serving normally regardless (§9.2/§13.6).
- **Depends on:** 1A, 1B, 1D (all Tier 1, merged).
- **Owns:** `backend/app/routes/search.py`, `queue.py`, `decisions.py`,
  `saved.py`.
- **Tests (§15.3 backend half):** `httpx.AsyncClient` vs. a real test
  SQLite DB, full contract per endpoint incl. the external-downtime
  error code and no stack-trace leakage.

**3B — Zotero endpoints** (§10.4 zotero rows)
- `GET /zotero/auth/start`, `GET /zotero/auth/callback`,
  `GET /zotero/collections`, `POST /zotero/collections`,
  `POST /zotero/push`.
- **Depends on:** 1A, 1C (merged).
- **Owns:** `backend/app/routes/zotero.py`.
- **Tests (§15.3, §15.7 automated tier):** session-mismatched callback
  rejected; successful flow stores encrypted `ZoteroConnection`; push
  returns per-PMID status, never all-or-nothing.

**3C — CSV export endpoint** (§8.8, §10.4 export.csv)
- `GET /export.csv`, streaming; CSV/formula-injection neutralization for
  fields starting with `=`, `+`, `-`, `@`; blank (not error) for
  missing-DOI rows (§13.4).
- **Depends on:** 1A only.
- **Owns:** `backend/app/routes/export.py`.
- **Tests (§15.1):** adversarial field values (`=1+1`, `+CMD(...)`)
  neutralized; correct column set; missing-DOI row exports cleanly.

**Wave 2 (solo, depends on Wave 1 merged): Task 3D — Cross-cutting
middleware** (§10.3, §10.5, §10.7)
Moved out of Wave 1 in this revision — the first draft listed it as
parallel to 3A/3B/3C despite its own test gate requiring their routes to
already exist ("tested against them"). It genuinely cannot run
concurrently with the routes it wraps and verifies.
- Consistent error-shape exception handler (§10.3, using Task 0.2's
  pinned shape).
- Per-`session_id`/per-IP inbound rate limiting via `slowapi` (§10.5) —
  a distinct code path from 1B's outbound pacing, tested separately.
- CORS allow-list + `allow_credentials` as the CSRF defense (§10.7):
  every state-changing route in 3A/3B/3C must reject non-JSON bodies.
- Baseline security headers.
- **Owns:** `backend/app/middleware/errors.py`, `ratelimit.py`,
  `security.py`.
- **Tests (§15.3, §15.8 inbound half):** requests past the per-session
  threshold get `429` (separate test from outbound-pacing tests); a
  non-JSON-body request from a disallowed origin never reaches any of
  3A/3B/3C's handlers; a deliberately-thrown exception never leaks
  message/stack.

**Tier 3 exit gate:** Wave 1's three route groups merged and
integration-tested; then Wave 2's middleware verified against all of
them.

---

## Tier 4 — Frontend↔backend integration (parallel — 3 subagents, depends on Tier 2 + Tier 3)

Wiring, not new logic. This tier's own tests exist to catch
integration-only bugs (shape mismatches, timing assumptions) — Task
0.2's pinned contracts should make these rare, not eliminate the need to
check.

**4A — Core loop wiring** (§11.4, ties 2C/2D to 3A)
- TanStack Query hooks point at real 3A endpoints instead of MSW.
- Single decision function (§11.4): swipe (Framer Motion), tap/click,
  keyboard all call it; triggers optimistic update, `PATCH /decisions`,
  next-card abstract prefetch (§5.6).
- 2D's playback engine consumes the *real* `/papers/{pmid}/abstract`
  response — since both sides built against Task 0.2's pinned shape,
  this should be a swap of data source, not a rewrite; a real shape
  mismatch here is exactly the signal that Task 0.2 wasn't followed and
  should be treated as a process bug, not just a code bug.
- **Tests (§15.3 frontend half, §15.10):** Playwright+MSW happy-path
  journey (§4.1); Playwright real drag-gesture test; unit test confirming
  swipe/tap/keyboard produce identical decision-function calls.

**4B — Zotero export wiring** (ties 2B's push sub-flow to 3B)
- OAuth redirect round-trip through 2A's callback route.
- Collection list/create, push with partial-failure states (§5.5),
  Disconnect Zotero (§5.4/§9.6).
- **Tests (§15.3, §15.7 automated tier, frontend side):** Playwright+MSW
  for success/connection-failure/push-failure states. Real-Zotero manual
  smoke test is Tier 6.

**4C — Offline & error-handling unification** (§11.7, §4.5, §13.6)
- Shared error-rendering component consuming Task 0.2's error shape,
  specialized only by copy per context (§4.3/§4.4/§4.5/§5.3a/§5.5),
  including the distinct §13.6 "external service unavailable" copy vs.
  the §4.5 "you're offline" copy — these must not collapse into one
  generic message, since 3A's `service_unavailable` code (Task 3A) is
  what distinguishes them.
- "Pending — will retry" states, automatic retry on reconnect.
- Cookie-consent notice (§10.2).
- **Tests (§15.6):** Playwright network-offline emulation — cached shell
  loads, in-progress session doesn't crash, queued actions retried on
  reconnect; separate test asserting the external-downtime message
  appears (mocked 3A `service_unavailable` response) while the app
  correctly reports itself as online.

**Tier 4 exit gate:** happy-path and major edge-case journeys (§4.1-4.7,
§13.6) pass end-to-end against the real backend on local/dev infra.

---

## Tier 5 — Deployment & CI infra (parallel — 2 subagents; starts as early as Tier 0 finishes)

**5A — Infra provisioning**
- Turso DB created; connection verified through **Task 0.1's `db.py`
  module** (not a separate ad hoc connection script) — this is the fix
  for the first draft's gap where 5A and 1A would otherwise have built
  two different DB-connection paths that someone had to reconcile later.
- Render free web service connected to the repo (§12.2).
- GitHub Pages / Cloudflare Pages connected (§12.2).
- All secrets created — `NCBI_API_KEY`, `NCBI_TOOL`, `NCBI_EMAIL`,
  `ZOTERO_CLIENT_KEY`, `ZOTERO_CLIENT_SECRET`, `TURSO_DATABASE_URL`,
  `TURSO_AUTH_TOKEN` (verify it's scoped to this DB only, not
  account-wide — §12.3 flags this explicitly), `SESSION_COOKIE_SECRET`,
  `TOKEN_ENCRYPTION_KEY` — created before feature code lands.
- **Test gate:** deploy the Tier-0 skeleton app (using `db.py`) to
  Render, write one row to Turso via that same module, confirm it
  survives a manual spin-down/restart cycle (§12.1's whole reason for
  choosing Turso). Do not deploy real feature code before this passes
  once.

**5B — CI/CD workflows**
- PR-gate: `ruff`/`mypy` + `tsc`/ESLint + both test suites, blocking
  merge (§12.4) — the automated enforcement of every tier gate above.
- Dependabot on both manifests.
- Merge-to-`main`: frontend build → Pages; Render auto-deploys via its
  own git integration.
- **Depends on:** 5A's secrets (for any step needing them).
- **Test gate:** open a throwaway PR with a deliberately failing test,
  confirm the pipeline blocks merge, before trusting it for real work.

**Tier 5 exit gate:** a real (empty) app is live on real infra through
the shared `db.py` module; CI actually blocks failing PRs.

---

## Tier 6 — Full-system test pass (parallel — 6 subagents, depends on Tier 4 + Tier 5)

Runs against the real deployed system. **6F is scheduled to avoid
interfering with 6A/6E**: since 6F deliberately drives the inbound rate
limiter (3D) into its throttling threshold, it either runs against a
dedicated test session/IP pool distinct from 6A/6E's traffic, or is
sequenced after 6A/6E finish rather than run concurrently against the
same shared deployment — the first draft ran all six blind to this
interference risk.

- **6A — Cross-browser/device** (§15.4): Playwright's three engines
  automated; manual pass on real Mobile Safari / Android Chrome for
  voice list, background-audio behavior (§13.2), install flow.
- **6B — PWA install** (§15.5): Lighthouse CI + manual install pass.
- **6C — OAuth real-Zotero smoke test** (§15.7 manual tier): against a
  real Zotero sandbox account.
- **6D — TTS synchronization, live** (§15.9): golden-file
  tokenizer/timing checks against real narration on real devices.
- **6E — Gesture testing, live** (§15.10): Playwright real mouse/touch
  against the deployed frontend.
- **6F — PubMed rate limiting under load** (§15.8): outbound (1B) and
  inbound (3D) limiters under concurrent simulated sessions, isolated or
  sequenced per the note above.

**Tier 6 exit gate — ship criteria:** all six tracks pass (automated
green in CI; manual signed off on a release checklist).

---

## Summary table

| Tier | Depends on | Structure | Gate |
|---|---|---|---|
| 0 | — | 3 sequential tasks | Scaffolding boots; contracts + fixtures committed |
| 1 | 0 | Wave 1: 1A solo → Wave 2: 1B/1C/1D parallel | Each module's tests green, in order |
| 2 | 0 | 4 parallel (shell, screens, state, playback) | Each module's tests green (fixture-based) |
| 3 | 1 | Wave 1: 3A/3B/3C parallel → Wave 2: 3D solo | Routes tested vs. real DB, then middleware vs. routes |
| 4 | 2, 3 | 3 parallel (core wiring, Zotero wiring, offline/errors) | End-to-end journeys pass locally |
| 5 | 0 (parallel to 1-4) | 2 parallel (infra, CI) | Hello-world persists a restart via shared `db.py`; CI blocks a failing PR |
| 6 | 4, 5 | 6 parallel, 6F isolated/sequenced | All six sign off |

---

## What changed after adversarial review

The first draft claimed several tasks were parallel-independent when
they weren't: 1A/1C shared a hard dependency (fixed by splitting Tier 1
into two waves), 3D required 3A/3B/3C's routes to exist before its own
tests could run (fixed by splitting Tier 3 into two waves), and no shared
contract existed for the segmented-abstract shape that 1D/2D/3A all
needed to agree on (fixed by adding Task 0.2). The review also found no
instruction guaranteeing agents in a "parallel" tier are actually
dispatched together, no named owner for merges or partial-wave failure,
a duplicated-logic risk between the backend tokenizer and a hedged
frontend port, an ownership gap on the DB-connection module between
5A and 1A, no shared fixture corpus (backend and frontend tests could
silently cover different edge cases), several §13 edge cases (§13.2
Wake Lock, §13.3 language mismatch, §13.4 retracted badge, §13.6 external
downtime, §13.7 no-Web-Speech-support) with no corresponding build task,
and a Tier 6 interference risk between the rate-limit load test and the
concurrent browser/gesture tracks. All are addressed above.

---

## Agent Assignments & Validation Checkpoints

Six subagents exist under `.claude/agents/`: `senior-backend-developer`,
`senior-frontend-developer`, `senior-fullstack-developer`, `tester`,
`adversarial-generalist`, and `user`. This section maps every task above
to who does it, and states the actual validation sequence that gates
moving on — not just "tests pass," but who checks what, in what order,
before a merge is real.

Every one of the five build-pipeline agents (all but `user`) keeps a
running `logs/<agent-name>.build.log` at the repo root, with an entry on
starting a task, on any notable pivot, and on finishing — this is how the
human tracks progress instead of meeting with each agent directly. The
validation-checkpoint pattern below assumes the human is reading these
logs, not sitting in on the work.

### Validation-checkpoint pattern (the same shape at every task/wave boundary)

1. The assigned specialist implements the task and writes its own tests,
   logging a START entry when picking up the task and a COMPLETE entry
   (with actual test results) when done.
2. `tester` independently verifies the task's cited §15 subsection is
   genuinely covered and green — not "some test exists" — and logs its
   own verdict, including any coverage gap even if the specialist's log
   claimed success.
3. `adversarial-generalist` reviews the diff against its SPEC.md
   citation for the known regression classes (session fixation, XSS, CSV
   injection, false task-independence, leaked stack traces, etc.) before
   merge, logging findings (or an explicit "nothing survived scrutiny").
4. The orchestrator merges only once it has checked — not recalled from
   a summary — that both a `tester` VERIFY entry and an
   `adversarial-generalist` REVIEW entry actually exist in their logs for
   this exact task ID; a specialist's own COMPLETE entry is never
   sufficient on its own. Any `blocking` finding from step 3 overrides a
   "gate met" verdict from step 2 regardless of order — this precedence
   is asymmetric by design. The orchestrator logs the merge decision (and
   any significant/minor-finding call it had to make) to
   `logs/orchestrator.log`, and posts a rollup line to `logs/status.log`
   once the wave containing this task closes. A wave is not "done" on a
   partial pass — a failing task blocks the wave/tier gate per the
   partial-failure rule above, regardless of how many sibling tasks
   passed. If the orchestrator can't resolve a disagreement between steps
   2 and 3 (or with a specialist disputing a finding) within two
   round-trips, it escalates to the human, logged as such.
5. At the end of Tier 4 and again at Tier 6, the human may additionally
   invoke `user` on demand for naive first-time UX feedback. This is
   optional and non-blocking — `user` reports only to the human,
   conversationally, and keeps no build.log, since it isn't a pipeline
   participant. If a finding from this is worth acting on, the human's
   go-ahead gets logged as a new task entry in the owning specialist's
   build.log before any fix is dispatched, so it enters the same durable
   handover system as everything else rather than staying word-of-mouth.

### Task → agent table

| Task | SPEC.md §§ | Primary agent | Also involved | Checkpoint |
|---|---|---|---|---|
| 0.1 Repo/tooling/`db.py` scaffolding | §10.1, §11.1 | `senior-fullstack-developer` | `tester` (smoke check) | Both apps boot; `db.py` connects to local SQLite and a Turso-style URL |
| 0.2 Shared data contracts (`CONTRACTS.md`) | §6.5, §8.7, §10.3, §10.4 | `senior-fullstack-developer` | `adversarial-generalist` (citations check) | Contract committed; later tasks reference it, don't invent shapes |
| 0.3 Shared fixture corpus | §6.5, §15.1, §15.9 | `senior-fullstack-developer` | `tester` | Fixtures committed; 1D/2D/1B/2C point at them, not private copies |
| 1A Data model & session identity (Wave 1) | §9, §10.2 | `senior-backend-developer` | `tester` → `adversarial-generalist` | CSPRNG/rotation/Fernet/binding-primitive tests green; security-citation review before Wave 2 starts |
| 1B PubMed client | §7 | `senior-backend-developer` | `tester` → `adversarial-generalist` | Fake-clock pacing, zero-result, iCite-degradation tests green |
| 1C Zotero client & OAuth handshake | §8 | `senior-backend-developer` | `tester` → `adversarial-generalist` (session-binding regression check) | Binding-enforcement, fixed-redirect, partial-batch tests green |
| 1D Text normalization & tokenizer | §6.3-§6.5, §13.3 | `senior-backend-developer` | `tester` (golden-file corpus) → `adversarial-generalist` | No mid-sentence splits on fixture corpus; language-mismatch flag correct |
| 2A App shell/PWA/routing | §11.1, §11.5, §11.6 | `senior-frontend-developer` | `tester` | Lighthouse installability check passes |
| 2B UI screens (+ Claude Design port) | §5, §13.1, §13.4 | `senior-frontend-developer` | `tester` → `adversarial-generalist` (XSS-rendering check) | Per-state rendering tests + safe-array text-rendering regression test green |
| 2C State scaffolding | §11.2 | `senior-frontend-developer` | `tester` | Store-transition unit tests green |
| 2D Playback engine | §6, §11.3, §13.2, §13.7 | `senior-frontend-developer` | `tester` → `adversarial-generalist` (duplicated-logic check vs. 1D) | Timer-fallback, mute-clock, speed-scaling, cancellation tests green |
| 3A Core loop endpoints | §7.9, §10.4, §13.6 | `senior-backend-developer` | `tester` → `adversarial-generalist` | Full contract tests vs. real test DB, incl. `service_unavailable` path |
| 3B Zotero endpoints | §10.4 | `senior-backend-developer` | `tester` → `adversarial-generalist` (OAuth regression check) | Session-mismatch rejection, encrypted storage, per-PMID push status tests green |
| 3C CSV export endpoint | §8.8, §10.4, §13.4 | `senior-backend-developer` | `tester` → `adversarial-generalist` (injection check) | Adversarial-field neutralization + missing-DOI tests green |
| 3D Cross-cutting middleware (Wave 2) | §10.3, §10.5, §10.7 | `senior-backend-developer` | `tester` → `adversarial-generalist` | Inbound-429, CORS/CSRF, no-stack-leak tests green vs. merged Wave 1 routes |
| 4A Core loop wiring | §11.4, §15.10 | `senior-fullstack-developer` | `tester` → `adversarial-generalist` | Happy-path journey + all-modality decision-function tests green |
| 4B Zotero export wiring | §5.5, §8 | `senior-fullstack-developer` | `tester` → `adversarial-generalist` | Success/failure/partial-failure Playwright+MSW tests green |
| 4C Offline & error-handling unification | §4.5, §11.7, §13.6 | `senior-fullstack-developer` | `tester` → `adversarial-generalist` | Offline-emulation + distinct-error-copy tests green |
| *(end of Tier 4, optional)* | §2.3 user stories | — | **`user`** (on demand) | Naive-user journey feedback, reported directly to the human, non-blocking |
| 5A Infra provisioning | §12.1-§12.3 | `senior-backend-developer` (or the human directly — ops work) | `tester` (restart-persistence check) | Hello-world app survives a Render spin-down/restart via shared `db.py` |
| 5B CI/CD workflows | §12.4 | `senior-backend-developer` (or the human directly) | `tester` | A deliberately-failing throwaway PR is actually blocked |
| 6A Cross-browser/device | §15.4 | `tester` | human (manual Mobile Safari/Android pass) | Playwright 3-engine suite green; manual checklist signed off |
| 6B PWA install | §15.5 | `tester` | human (manual install pass) | Lighthouse CI green; manual install confirmed on real devices |
| 6C OAuth real-Zotero smoke test | §15.7 | human (needs a real Zotero account) | `tester` (result review) | Real sandbox flow completes end-to-end |
| 6D TTS synchronization, live | §15.9 | `tester` | `senior-frontend-developer` (fixes) | Golden-file timing checks hold on real devices |
| 6E Gesture testing, live | §15.10 | `tester` | `senior-frontend-developer` (fixes) | Real touch/mouse emulation green against deployed frontend |
| 6F Rate limiting under load | §15.8 | `tester` | `senior-backend-developer` (fixes) | Outbound + inbound limiters hold under load, isolated from 6A/6E |
| *(Tier 6, optional)* | §2.3 user stories | — | **`user`** (on demand) | Final naive-user pass on the live deployed app |

### Happy path, end to end

**Tier 0** — the full-stack agent scaffolds both apps and pins
`CONTRACTS.md`/the fixture corpus in one pass; `tester` confirms both
apps boot. **Tier 1** — the backend agent lands session identity first
(Wave 1), then PubMed, Zotero, and the tokenizer in parallel (Wave 2),
each independently tested and adversarially reviewed before merge.
**Tier 2** — the frontend agent builds shell, screens, state, and
playback engine in parallel against fixtures, same test-then-review
pattern, running concurrently with Tier 1 since neither depends on the
other's implementation. **Tier 3** — the backend agent composes Tier 1's
modules into routes (Wave 1: core/Zotero/CSV in parallel), then adds
cross-cutting middleware once those routes exist to test against
(Wave 2). **Tier 4** — the full-stack agent wires frontend to backend in
three parallel seams, with the human optionally calling in `user` for a
gut-check once there's a real UI. **Tier 5** — infra and CI stand up in
parallel with all of the above, gated on their own hello-world/
failing-PR checks. **Tier 6** — `tester` runs the full cross-cutting
validation sweep against the live deployment, the human runs the one
step that needs a real Zotero account, and `user` gets one last look
before shipping. At every step, the human's read on progress comes from
the five build.logs, not a meeting.
