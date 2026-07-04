# LitList — Product & Technical Specification

This document is the single source of truth for LitList, built up section by
section. Each section is drafted, reviewed by the product owner, and only
then marked final. Sections are added in this order:

1. Vision & Product Philosophy ✅
2. Personas & User Stories ✅
3. Information Architecture ✅
4. Complete User Journeys ✅
5. UI Wireframes ✅
6. Audio/TTS System ✅
7. PubMed Integration ✅
8. Zotero Integration ✅
9. Data Model ✅
10. Backend API Specification ✅
11. Frontend Architecture ✅
12. Deployment & CI ✅
13. Accessibility & Edge Cases ✅
14. Future Roadmap ✅
15. Test Plans ✅ (this section, and the final one)

---

## 1. Vision & Product Philosophy

### 1.1 One-line pitch

LitList turns a literature search into a hands-free, audio-narrated stack of
papers you can triage by swiping — like screening a dating app, but for
what you'll actually read.

### 1.2 Problem

Researchers accumulate literature-review backlogs faster than they can
process them. Reading titles and abstracts to decide "is this worth a full
read?" is a screen-bound, eyes-and-hands task that competes with commutes,
walks, chores, and other dead time. Reference managers like Zotero are good
at *storing* papers but do nothing to help *triage* them, and PubMed's own
interface is built for search, not for rapid sequential review.

### 1.3 Product philosophy

- **Screening, not reading.** LitList's job ends at "is this worth saving
  for later?" — it is explicitly not a paper reader, summarizer, or PDF
  viewer. The output of a session is a curated Zotero collection or CSV,
  not annotated papers.
- **Hands-free first, hands optional.** The primary mode of consumption is
  audio, so the app is usable while walking, commuting, or doing chores.
  Every swipe interaction has a no-touch equivalent (auto-advance,
  configurable default action) so a session can run entirely passively if
  the user chooses.
- **Fast triage over deep configuration.** Settings (what's read aloud,
  sort order, default swipe behavior) are set once per search, then get out
  of the way. The steady-state screen is just: what's playing, what's next,
  swipe or wait.
- **Free and open by default.** LitList is a free tool for researchers, not
  a monetized product. Technology choices throughout this spec favor
  open-source and free-tier services over paid SaaS, even where a paid
  option would be marginally more polished — cost and openness are treated
  as first-class product requirements, not afterthoughts.
- **Own your data, own your workflow.** LitList does not try to replace
  Zotero or become a new silo — saved papers are pushed into the reference
  manager the user already uses (or exported as CSV for anything else).
  LitList holds no long-term ownership over the user's reading list.
- **Augment judgment, don't replace it (yet).** V1 makes no attempt to
  predict what the user wants — sorting is by transparent, explainable
  signals (relevance, recency, citation count), not a black-box model. A
  swipe-history-driven recommendation engine is an explicit future
  possibility (see Future Roadmap) but is deliberately out of scope now, so
  the core screening loop stays simple, predictable, and trustworthy before
  any personalization is layered on.

### 1.4 What LitList is not (v1 scope boundaries)

- Not a PDF reader or full-text viewer.
- Not a note-taking or annotation tool.
- Not a citation manager in its own right — Zotero remains the system of
  record for saved papers.
- Not a recommendation/discovery engine — search queries come from the
  user, not from the app guessing interests.
- Not a multi-format audio product yet — v1 ships one narration format
  (plain sequential TTS: title → metadata → abstract). Podcast-style
  narration (e.g. conversational framing, multiple papers woven into a
  segment) is a named future direction, not a v1 requirement.

### 1.5 Success looks like

A researcher opens LitList during a walk, runs a search, and by the time
they're back at their desk has a Zotero collection of 10-20 papers worth a
real read — without having looked at their phone screen for more than the
few seconds it took to type the search and occasionally swipe.

---

## 2. Personas & User Stories

### 2.1 Primary persona: The Backlogged Researcher

**Who they are.** A grad student, postdoc, PI, or industry R&D scientist
who runs literature searches regularly (weekly alerts, project kickoffs,
grant writing, staying current in a subfield) and has more candidate papers
than time to properly triage them. Comfortable with Zotero or another
reference manager as their system of record. Owns a smartphone and spends
real time in states where screens are inconvenient (commuting, walking,
lab work, chores, exercise).

**Goals.**
- Convert "dead time" (walks, commutes, chores) into literature-screening
  time.
- End a session with a shortlist of papers worth a real read, already
  sitting in their existing reference manager.
- Avoid the two failure modes of manual triage: reading too shallowly (miss
  something good) or too deeply (waste time on something irrelevant).

**Frustrations today.**
- PubMed's UI is built for searching, not for rapid sequential
  yes/no screening of results.
- Reading paper-by-paper on a phone screen while walking is unsafe and
  impractical.
- Existing TTS "read this page to me" browser tools don't understand paper
  structure (title vs. authors vs. abstract) and read noisy metadata badly.
- Manually copying papers of interest into Zotero one at a time is tedious
  when the source isn't already a Zotero-connector-supported page.

**Relationship to the product.** This persona is both the primary and
(for v1) *only* target user — LitList is not being designed for
non-researchers, students doing casual reading, or literature outside the
biomedical/life-science scope of PubMed. Secondary audiences (e.g.
researchers who use Semantic Scholar or other databases instead of PubMed)
are explicitly out of scope until PubMed coverage is validated.

### 2.2 Secondary persona: The Journal-Club Curator

**Who they are.** Someone (often a lab's senior student or postdoc)
responsible for surfacing candidate papers for a recurring journal club or
lab meeting. Runs broader, more exploratory searches than the primary
persona and cares more about volume-screening than deep personal interest.

**Goals.**
- Quickly narrow a broad search (e.g. a whole subfield for the month) down
  to a handful of discussion-worthy candidates.
- Export a shortlist in a format that's easy to share with a group,
  independent of whether everyone uses Zotero (hence CSV export mattering
  as much as the Zotero push for this persona).

**Note.** This persona doesn't require new capabilities beyond what the
primary persona needs — it validates that both save paths (Zotero push
*and* CSV export) matter, not just Zotero.

### 2.3 User stories

Written as `As a [persona], I want to [action], so that [outcome]`,
grouped by the phase of the core loop.

**Search & configure**
- As a researcher, I want to enter a free-text PubMed query, so that I can
  start screening papers on any topic without leaving the app.
- As a researcher, I want to choose how results are sorted (relevance,
  recency, citation count), so that the order matches what I care about for
  this particular search.
- As a researcher, I want to choose which metadata fields are read aloud
  (last author, journal, publication date), so that I hear only the
  context that helps me decide, without the audio getting bloated.
- As a researcher, I want to set what happens by default when I don't
  swipe (auto-save vs. auto-skip), so that a passive, hands-off session
  still produces a sensible outcome.
- As a researcher, I want my search and settings to persist so that
  starting a new, related search doesn't mean reconfiguring everything from
  scratch.

**Listen & triage**
- As a researcher, I want to press one large play button and have papers
  narrated to me back-to-back, so that I can screen literature without
  looking at my phone.
- As a researcher, I want to hear the title first, then a short
  configurable metadata line, then the abstract, so that I get the most
  decision-relevant information in the most useful order.
- As a researcher, I want to swipe right/left at any point — even mid-
  narration — to save or skip a paper immediately, so that I don't have to
  wait for narration to finish once I've made up my mind.
- As a researcher, I want the abstract text to appear on screen with the
  currently-spoken sentence highlighted, so that if I do glance at my
  phone, I can follow along or skim ahead.
- As a researcher, I want a clear audio cue (chime/beep) between papers, so
  that I know, without looking, when one paper has ended and the next has
  begun.
- As a researcher, I want to pause and resume the narration stream at any
  point, so that I can handle an interruption (a phone call, crossing a
  street) without losing my place.
- As a researcher, I want to control playback speed, so that I can match
  the pace to my environment and familiarity with the subfield.
- As a researcher without earphones (or who simply doesn't want audio in
  the moment), I want to tap a mute button and keep triaging by reading
  the highlighted text on screen, so that the app is still useful when
  audio isn't practical or wanted — without the experience otherwise
  changing (same speed, same highlight, same swiping).

**Review & export**
- As a researcher, I want to see the list of papers I've saved during a
  session, so that I can review my choices before committing them anywhere.
- As a researcher, I want to push my saved papers directly into a Zotero
  collection (existing or new), so that they land where I already manage
  my reading list without manual re-entry.
- As a journal-club curator, I want to export my saved papers as a CSV, so
  that I can share a shortlist with people who don't use Zotero.
- As a researcher, I want to authenticate with Zotero once and be
  remembered, so that pushing saved papers doesn't require logging in
  every session.

**Iterate**
- As a researcher, I want to revise my previous search terms and settings
  and re-run the loop, so that I can screen a related or follow-up topic
  without starting completely from scratch.

### 2.4 Explicit non-goals for personas

- No support (in v1) for collaborative/shared screening sessions (e.g. a
  lab jointly triaging the same queue in real time).
- No account tiers, teams, or admin roles — every user has the same
  capabilities; the only external identity involved is Zotero's own OAuth.

---

## 3. Information Architecture

### 3.1 Overview

LitList is a **single-page app with one primary surface** (the "Stack
Screen") and **two collapsible panels** that slide over it — there is no
traditional multi-page navigation, tab bar, or hamburger menu. The whole
IA is built around one vertical gesture axis (swipe up/down = which panel
is showing) and one horizontal gesture axis (swipe left/right = decide on
the current paper). This mirrors the single sketched user journey exactly:
panels are peeled back to configure, then collapsed to consume.

```
┌─────────────────────────────┐
│   SEARCH & SETTINGS PANEL    │  ← revealed by swiping down from top
├─────────────────────────────┤
│                               │
│        STACK SCREEN          │  ← default/home surface
│   (player + current queue)   │
│                               │
├─────────────────────────────┤
│      SAVED LIST PANEL        │  ← revealed by swiping down from
└─────────────────────────────┘     Stack Screen a second time / a
                                     dedicated gesture (see 3.3)
```

### 3.2 Top-level structure

**A. Auth Gate** (shown only when required)
- Login screen. Per the vision, login should be as frictionless as
  possible — the app must be usable to search and preview without forcing
  login; login is only required at the point of pushing to Zotero, since
  Zotero is the only external identity involved (see 2.4). This is
  revisited in the Zotero Integration section.

**B. Stack Screen** (the home surface, default view on app open)
- Persistent elements:
  - Large **play/pause button** (bottom, primary control).
  - **Mute button** (small, next to/near the play button) — toggles audio
    output only; playback, highlighting, timing, and auto-advance all
    keep running exactly as before (see 2.3's no-earphones story). There
    is no separate "silent mode" — muting is just one toggle on the same
    single playback engine.
  - **Current paper card** (title visible above the fold; abstract text
    revealed/highlighted during playback).
  - **Next-up preview** (small, directly under the play button — title
    only, no audio).
  - Ambient affordance hinting the Search & Settings panel is above
    (swipe-down) and the Saved List panel is below, under the play button
    (swipe-up).
- Transient elements (appear during playback, muted or not):
  - Sentence-level highlighted abstract text (karaoke-style), advancing in
    sync with playback at the rate set by the single Speed control in the
    Search & Settings Panel — unaffected by the mute toggle.
  - Swipe-away animation on decision.
  - End-of-paper chime (skipped/replaced by a visual pulse only while
    muted) + auto-swipe/auto-advance (always).

**C. Search & Settings Panel** (revealed by swiping down over the Stack
Screen)
- Search bar (free-text query → PubMed).
- Sort control (relevance / recency / citations).
- Read-aloud field toggles (last author, journal, publication date).
- Default swipe-behavior toggle (unswiped → "Interested" vs. "Not
  interested").
- Speed control — a single setting that drives narration rate; the
  sentence-highlight always advances in lockstep with narration timing
  (muted or not), so there's only one pace to reason about.
- Narration format selector (v1: audiobook/TTS only, disabled/greyed
  options previewing the future podcast format — see Future Roadmap).
- Collapses back to the Stack Screen via swipe-up, which also (re)starts
  or updates the queue per 4.x journeys.

**D. Saved List Panel** (docked under the play button on the Stack Screen;
revealed by swiping up, collapses back by swiping down — see 3.3)
- List of papers marked "Interested" this search session. (Persisting the
  Saved List across search sessions is a future direction, not v1 — see
  Future Roadmap. In v1 it reflects only the current session.)
- Per-item minimal metadata (title, journal, date) with a remove/undo
  affordance.
- Two export actions: **Push to Zotero** and **Download as CSV**.
- Zotero push sub-flow: authenticate (if not already) → choose existing
  collection or create new → confirm → success/failure state.

### 3.3 Navigation model

Three vertical zones stacked on one axis — Search & Settings above, Stack
Screen in the middle, Saved List below — plus the independent horizontal
decision gesture on the current card:

| Gesture | Context | Result |
|---|---|---|
| Swipe down (from top of Stack Screen) | Stack Screen | Reveal Search & Settings Panel |
| Swipe up | Search & Settings Panel | Collapse to Stack Screen |
| Swipe up (from under the play button on Stack Screen) | Stack Screen | Reveal Saved List Panel |
| Swipe down | Saved List Panel | Collapse to Stack Screen |
| Swipe right | Stack Screen, on current card | Mark current paper "Interested" → advance |
| Swipe left | Stack Screen, on current card | Mark current paper "Not interested" → advance |
| Tap | Play/pause button | Toggle narration playback |
| Tap | Mute button | Toggle audio output only — no effect on playback/highlight timing |

The Search & Settings Panel and the Saved List Panel sit on opposite sides
of the Stack Screen (above vs. below), so swipe-down and swipe-up are
never ambiguous — down always means "go toward search," up always means
"go toward saved."

### 3.4 Content hierarchy per paper (what a "paper" surfaces, in order)

This ordering drives both the audio narration order (Audio/TTS System
section) and the on-screen text reveal order:

1. Title (always shown/read)
2. Configurable metadata line (last author, journal, publication date —
   user-selected subset, read as a single short line)
3. Abstract (read in full, sentence-highlighted on screen)
4. Implicit metadata used for sorting/filtering but not necessarily read
   aloud: relevance score, citation count, publication date (if not
   selected for narration it still governs the "recency" sort).

### 3.5 Session & state scope

- **Search session**: one query + its sort/settings + its resulting queue
  + swipe decisions made against it, including the Saved List built up
  during it. In v1, starting a new query (step 18 in the journey) starts a
  fresh session and a fresh Saved List — the expectation is that a user
  reviews/exports the Saved List (Zotero push or CSV) before or as part of
  moving to a new search. Persisting/accumulating the Saved List across
  multiple search sessions is a named future direction (see Future
  Roadmap), not v1 behavior.
- **Settings** (read-aloud fields, default swipe behavior, playback speed)
  are scoped per-search-session by default but pre-fill from the previous
  session's values (per journey step 18: "I see the earlier search and
  settings pre-filled") — i.e. they act as a sticky default, not a global
  fixed config.
- **Saved List** is the hand-off point to Zotero/CSV for the current
  session; see above for why cross-session accumulation is deferred.

### 3.6 Out of scope for the IA (v1)

- No settings/profile page separate from the Search & Settings Panel —
  the only "settings" are the per-search ones already described, plus
  Zotero connection status (surfaced inline in the Saved List Panel's
  export flow, not a separate account page).
- No history/browsing of past search sessions as a distinct IA surface —
  only the most recent session's settings persist forward (3.5); the
  Saved List itself does not persist past the current session in v1.

---

## 4. Complete User Journeys

### 4.1 Primary journey — happy path, audio mode

This is the canonical flow, incorporating the resolved IA/navigation
decisions (swipe-down for Search & Settings, swipe-up for Saved List, one
unified Speed control).

1. **Land.** User opens the app on their phone (browser or installed PWA).
   No login is required yet — the Stack Screen shows an empty/idle state
   with a prompt to swipe down to search.
2. **Search.** User swipes down to reveal the Search & Settings Panel and
   types "computational neuroscience spiking neural networks."
3. **Configure results.** The app queries PubMed and returns a result set.
   The user picks Sort by "relevance" (vs. recency/citations) and the
   queue reorders accordingly.
4. **Configure narration.** User selects that last-author name, journal,
   and publication date should all be read as the metadata line (the full
   v1 field set — see 3.2.C).
5. **Configure default behavior.** User sets the unswiped-default to "Not
   interested" — i.e. papers that play out fully without a swipe are
   treated as skipped, not saved.
6. **Collapse to Stack Screen.** User swipes up; the Search & Settings
   Panel closes, queue is loaded, current + next-up cards are populated.
7. **Play.** User taps the large play button.
8. **Narrate — heading.** TTS reads the title, pauses ~1s, then reads the
   configured metadata line (last author, journal, date), pauses ~1s.
9. **Narrate — abstract.** TTS begins reading the abstract. On-screen text
   appears in sync, sentence-by-sentence highlighting, at a rate governed
   by the Speed setting.
10. **No action taken — auto-decide.** The paper finishes narrating; the
    user did nothing. A chime plays, and per the configured default
    behavior, the paper is auto-marked "Interested" if that's what "no
    action" means for this session — auto-right-swipe animation plays, and
    the next paper begins automatically.

    *(Note: step 5 above set the default to "Not interested," so in this
    concrete run-through an un-swiped paper would in fact be auto-skipped,
    not auto-saved. This step is written generically to also cover the
    opposite default setting, which is the case originally sketched in the
    product brief.)*
11. **Mid-narration decision — skip.** On the next paper, partway through
    the abstract, the user decides it's not relevant and swipes left. A
    swipe-away animation plays immediately (narration for that paper stops
    early), and the next paper begins.
12. **Pause.** After several more papers, the user gets bored/arrives at a
    destination and taps pause. Narration and highlight-advance both halt
    and hold state (current sentence position retained for resume).
13. **Review saved list.** User swipes up from the Stack Screen (from
    under the play button) to reveal the Saved List Panel, showing every
    paper marked "Interested" so far this session.
14. **Export — Zotero.** User taps "Push to Zotero." Since this is the
    first export this session, the app prompts Zotero login/authorization.
    User authenticates, then chooses an existing collection or creates a
    new one, and confirms. The app pushes the saved papers (via DOI/
    metadata) into that Zotero collection and shows a success state.
15. **Verify externally.** (Outside the app) user opens Zotero and
    confirms the papers now appear in the chosen collection.
16. **Iterate.** User swipes down to reopen Search & Settings. Per 3.5,
    since they're changing the query, this starts a new search session:
    the query field is cleared to blank but the *settings* (metadata
    fields, default behavior, speed, sort choice) pre-fill from the
    previous session. User types "neurophysiology" and the loop restarts
    from step 3. The previous Saved List is not carried forward (v1
    scope — see 3.5/Future Roadmap); anything not yet exported should have
    been reviewed/exported before moving on.

### 4.2 Journey — muted (no-earphones) reading

Covers the no-earphones user story (2.3). There is no separate mode here
— the same playback engine from 4.1 runs unchanged; muting only silences
the audio output.

1. User completes search & settings configuration and taps play, as in
   4.1 steps 1-7.
2. User taps the mute button (5.x). Playback continues exactly as before
   — same Speed setting, same sentence-by-sentence highlight advance, same
   auto-decide/auto-advance timing — just without audible narration. The
   user follows along by reading the highlighted text on screen instead.
3. The end-of-paper cue becomes a visual pulse instead of an audible
   chime while muted (per Accessibility & Edge Cases); everything else
   (swiping mid-narration, auto-advance) behaves identically to 4.1.
4. Saved List review and export proceed identically to 4.1 steps 13-15.
   Unmuting at any point (including mid-paper) simply resumes audible
   narration in sync with the highlight that was already running.

### 4.3 Edge case — empty or near-empty search results

1. User searches a query that returns zero or very few PubMed results
   (e.g. an overly narrow or misspelled query).
2. On collapsing the Search & Settings Panel, the Stack Screen shows an
   explicit empty state (not a blank/broken player) — messaging that no
   papers matched, with a clear affordance to swipe down and revise the
   query immediately rather than getting stuck.
3. No queue, no play button interaction is possible in this state.

### 4.4 Edge case — Zotero authentication or push failure

1. User reaches step 14 of 4.1 (Push to Zotero) but authentication fails
   (bad credentials, denied permission) or the push itself fails (network
   error, expired token, Zotero API error).
2. The app surfaces a clear, specific error in the Saved List Panel
   (distinguishing "couldn't log in" from "logged in, but the push
   failed") and leaves the Saved List intact and unmodified — nothing is
   silently dropped or marked exported if it wasn't.
3. User can retry the push, or fall back to "Download as CSV" without
   losing their saved papers.

### 4.5 Edge case — interrupted / offline mid-session

1. User loses connectivity mid-session (e.g. entering a subway, spotty
   signal on a walk) after a queue has already been fetched from PubMed.
2. Papers already loaded into the current queue (title/metadata/abstract
   text, and, if pre-fetched, their TTS audio — see Audio/TTS System
   section for how much is pre-fetched vs. streamed) continue to be
   playable/readable offline.
3. Attempting to fetch a new page of results, start a new search, or push
   to Zotero while offline surfaces a clear "you're offline" state rather
   than failing silently or hanging.
4. On reconnect, queued actions that make sense to retry automatically
   (e.g. a Zotero push that failed only due to connectivity) may be
   retried — exact retry-vs-manual behavior is left to the Backend API /
   Frontend Architecture sections.

### 4.6 Edge case — decisive mid-narration swipe on every paper

1. A user who already knows exactly what they want swipes immediately
   (within the first second of the title, before metadata or abstract
   narration even begins) on every paper, never letting one play out.
2. The app must cleanly cancel/stop in-flight narration audio and any
   pending "auto-decide" timers the instant a swipe is registered, and
   move to the next paper's narration without overlap, delay, or audio
   artifacts from the previous paper bleeding through.

### 4.7 Edge case — revisiting/undoing a decision

1. While the Saved List Panel is open, the user notices a paper they
   swiped right on by mistake (or changes their mind) and removes it from
   the list before exporting (per the remove/undo affordance in 3.2.D).
2. Removing a paper from the Saved List does not return it to the live
   queue — the swipe-based queue only moves forward; undo only affects
   whether a decision is honored at export time, not resurrecting the
   card. (Re-surfacing skipped/removed papers is not a v1 requirement.)

---

## 5. UI Wireframes

This section resolves the two items left open in Sections 3-4 before
describing every screen:

- **No separate silent/text-only mode (resolved).** There is one playback
  engine and one play button. A small **mute** button next to it toggles
  only the audio output; the sentence-highlight, timing, auto-advance, and
  swiping all keep running identically whether muted or not. This is
  simpler than maintaining two parallel playback paths (an audio-driven
  clock and a separate timer-driven clock) and is the one thing a
  hands-busy user needs to find by feel: play to start, mute to go quiet.
- **Offline retry (resolved, minimal v1 behavior).** Actions that fail
  purely due to connectivity (Zotero push, new search) are marked
  "pending — will retry" in place and retried automatically once
  connectivity returns; the user can also force a manual retry at any
  time. No background sync beyond the current app session is implied.

### 5.1 Screen A — Idle / Landing

```
┌─────────────────────────────┐
│   ⌄  swipe down to search    │  ← subtle top affordance
│                               │
│                               │
│        L i t L i s t         │  ← wordmark, centered
│                               │
│   "Swipe down to search      │
│    PubMed and start          │
│    listening."                │
│                               │
│                               │
│           ⌃                  │  ← subtle bottom affordance
│   swipe up for saved list     │
│      (disabled — empty)       │
└─────────────────────────────┘
```
- Buttons: none active. Both swipe affordances are visible but the
  "saved list" one is visually de-emphasized/disabled since there's
  nothing saved yet this session.
- Gestures: swipe down → Screen B (Search & Settings). Swipe up → no-op
  toast ("Nothing saved yet") since the list is empty.
- Animation: wordmark has a slow idle fade/breathe (subtle, no distraction
  — this is a waiting state, not a marketing splash).
- No login prompt here — consistent with 3.2.A, auth is deferred until
  Zotero push.

### 5.2 Screen B — Search & Settings Panel

```
┌─────────────────────────────┐
│  ✕                    swipe ⌃│  ← close (or swipe up) to collapse
├─────────────────────────────┤
│ 🔍 [ computational neuro... ]│  ← search input, autofocus on open
├─────────────────────────────┤
│ Sort by:  (•)Relevance       │
│           ( )Recency          │
│           ( )Citations        │
├─────────────────────────────┤
│ Read aloud:                  │
│  [x] Last author              │
│  [ ] All authors              │
│  [x] Journal                  │
│  [x] Publication date         │
├─────────────────────────────┤
│ If I don't swipe:            │
│  ( )Mark Interested            │
│  (•)Mark Not Interested        │
├─────────────────────────────┤
│ Speed        [-----●----] 1.1x│  ← single control, audio + highlight
├─────────────────────────────┤
│ Format:  (•) Audiobook (TTS)  │
│          ( ) Podcast (soon)   │  ← disabled, greyed, tooltip "coming
│                                 later"
├─────────────────────────────┤
│         [  Start  ▶ ]        │  ← primary CTA, same action as swipe-up
└─────────────────────────────┘
```
- Buttons: search field (submits on enter/search-icon tap and also live-
  updates a result count if cheap to compute); sort radio group; checkbox
  list for narration fields; radio pair for default behavior; speed
  slider with numeric readout; format radio (podcast option present but
  disabled — visible so users know it's coming, not hidden); explicit
  "Start" button as a tap-alternative to the swipe-up gesture (accessibility
  and discoverability — not everyone will find the gesture unprompted).
- Gestures: swipe up anywhere on the panel, or tap ✕, or tap "Start" — all
  three collapse to Screen C and (re)build the queue from current field
  values.
- State: on second and later opens within a session, all fields pre-fill
  from the last-used values (3.5). The search text field itself is
  cleared to empty as the invitation to type a new query, per 4.1 step 16.
- Validation: "Start"/swipe-up is disabled (or produces the empty-state in
  5.3a) if the query field is blank — you cannot swipe into a queue with
  no search performed yet.
- Loading state: while PubMed results are being fetched/sorted, the panel
  shows a lightweight inline spinner near the search field rather than a
  full-screen blocker, so users can still adjust settings while waiting.

### 5.3 Screen C — Stack Screen (the home surface)

```
┌─────────────────────────────┐
│  ⌄ swipe down for search     │
├─────────────────────────────┤
│                               │
│  Spiking Neural Networks     │  ← title, always visible
│  for Real-Time Neuromorphic  │
│  Inference                   │
│                               │
│  ┌───────────────────────┐   │
│  │ Efficient spike-based  │   │  ← abstract text area;
│  │ encoding remains a     │   │    appears once playback starts;
│  │ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  │   │    current sentence highlighted
│  │ central challenge for  │   │    (▓ = highlighted run)
│  │ ...                     │   │
│  └───────────────────────┘   │
│                               │
│      Smith et al. · Nature   │  ← metadata line, per settings
│         Neuroscience · 2025  │    (read aloud AND shown on screen)
│                               │
│  ┌─────────────────────┐     │
│  │ Next: "Temporal      │     │  ← next-up preview card, title only
│  │ Coding in Cortical..." │    │
│  └─────────────────────┘     │
│                               │
│   (✕ Skip)  (♥ Interested)   │  ← tap/click decision buttons
│                               │
│           (  ▶  )     (🔇)   │  ← play/pause + small mute toggle
│                               │
│  ⌃ swipe up for saved list   │
└─────────────────────────────┘
```
- Buttons: the large play/pause circular button (primary), a small mute
  toggle beside it (🔇/🔊), and a pair of **decision buttons** (✕ Skip /
  ♥ Interested) — the tap/click/keyboard-accessible equivalent of the
  swipe gesture, required per Accessibility & Edge Cases (13.1) so mouse,
  motor-impaired, and screen-reader users aren't locked out of the core
  loop. Mute affects audio output only — it does not pause playback, does
  not affect the highlight, and does not require playback to be paused
  first.
- Card content order (matches 3.4): title always visible; metadata line
  and abstract are populated but the abstract stays collapsed/greyed
  until playback actually starts (muted or not), so a still card doesn't
  spoil the abstract before the user is engaged.
- Gestures/inputs on the current card — all four route through the same
  single decision function (11.4), so behavior never diverges by input
  method:
  - Swipe right, tap "♥ Interested", or press → (right arrow) → 5.3b
    (interested animation).
  - Swipe left, tap "✕ Skip", or press ← (left arrow) → 5.3b
    (not-interested animation).
  - Space bar → toggle play/pause; tap/click the mute icon or its
    keyboard equivalent → toggle mute (13.1).
  - Tap anywhere else on the card body → no-op in v1 (reserved — see 5.6
    note on reserved gestures).
  - Swipe down (from top strip) or ↓ → Screen B.
  - Swipe up (from under the play button) or ↑ → Screen D.
- Next-up preview: static, title-only, tapping it is a no-op (it exists
  purely as a preview so a hands-busy user isn't surprised by what's
  next; it becomes the current card automatically on advance).

### 5.3a Screen C — Empty results state

```
┌─────────────────────────────┐
│                               │
│         (no results)         │
│                               │
│   No papers matched           │
│   "asdkjalksdj 12931".        │
│                               │
│   Swipe down to try a         │
│   different search.           │
│                               │
│           ( ▶ )               │  ← disabled/greyed, non-functional
└─────────────────────────────┘
```
- Per 4.3: no queue exists, so the play button is visibly disabled
  (greyed, no tap response beyond a subtle "shake" affordance hinting
  it's inactive). Only the swipe-down gesture is live.

### 5.3b Swipe decision animation

- **Swipe right ("Interested")**: card translates off to the right with a
  slight upward arc and a green tint/checkmark overlay that fades in
  during the motion (~250-300ms), then the next-up card slides up into
  the current position from below.
- **Swipe left ("Not interested")**: card translates off to the left with
  a slight downward arc and a red/grey tint/X overlay, same timing, same
  next-card slide-in.
- **Auto-decide (unswiped, paper finishes narrating)**: identical
  animation to whichever direction matches the session's default-behavior
  setting, triggered automatically at narration-end instead of by touch,
  preceded by the end-of-paper chime, or an equivalent short visual pulse
  if muted — see Accessibility & Edge Cases.
- **Mid-narration swipe (4.6)**: identical visual animation; the audio
  layer must hard-stop the current utterance with no fade/crossfade
  bleed before the next paper's title narration begins.
- Card stack depth: only the current + next-up cards are ever rendered
  with content; anything beyond next-up exists only in the queue data
  structure, not pre-rendered in the DOM, to keep the animation cheap.

### 5.4 Screen D — Saved List Panel

```
┌─────────────────────────────┐
│  ⌄ swipe down to collapse    │
├─────────────────────────────┤
│  Saved this session (7)      │
├─────────────────────────────┤
│  Spiking Neural Networks...  │
│  Smith et al. · 2025    [✕]  │
├─────────────────────────────┤
│  Temporal Coding in...        │
│  Lee et al. · 2024      [✕]  │
├─────────────────────────────┤
│  ...                          │
├─────────────────────────────┤
│                               │
│  [ Push to Zotero ]           │
│  [ Download CSV   ]           │
│                               │
│  Connected to Zotero as you   │
│  [ Disconnect Zotero ]        │  ← only shown once connected
└─────────────────────────────┘
```
- Buttons: per-item [✕] remove (per 4.7, removes from list only, does not
  reopen the card in the queue); "Push to Zotero" primary action;
  "Download CSV" secondary action; a small "Disconnect Zotero" action,
  shown only once a `ZoteroConnection` exists (9.2), which deletes it
  immediately (9.6) — required per the OAuth security review (9.6) so
  the OAuth relationship isn't a one-way door with no in-app way back.
- Empty state (nothing saved yet): the two export buttons are disabled,
  with copy "Papers you mark Interested will show up here."
- Gestures: swipe down or tap outside the list to collapse back to Screen C.

### 5.5 Screen D1 — Zotero push sub-flow

```
Step 1: Not yet connected          Step 2: Choose collection
┌─────────────────────────┐        ┌─────────────────────────┐
│  Connect your Zotero      │        │  Save 7 papers to:        │
│  account to save papers.  │        │                            │
│                            │        │  (•) Reading List          │
│  [ Connect to Zotero ]    │  ───►  │  ( ) Neuro Journal Club     │
│                            │        │  ( ) + New collection...   │
└─────────────────────────┘        │                            │
                                     │  [ Cancel ]  [ Save ]      │
                                     └─────────────────────────┘

Step 3a: Success                    Step 3b: Failure
┌─────────────────────────┐        ┌─────────────────────────┐
│  ✓ Saved 7 papers to      │        │  ⚠ Couldn't save to      │
│  "Neuro Journal Club".    │        │  Zotero (network error). │
│                            │        │  Nothing was lost —       │
│  [ Done ]                 │        │  your list is unchanged.  │
└─────────────────────────┘        │                            │
                                     │  [ Retry ]  [ Download CSV]│
                                     └─────────────────────────┘
```
- Step 1 triggers Zotero's OAuth flow in a system browser tab/webview per
  standard OAuth practice (full mechanics in the Zotero Integration
  section); on return, the app proceeds straight to Step 2.
- Step 2's "+ New collection" expands an inline text field rather than
  navigating away.
- Step 3b matches 4.4: the error distinguishes connection failure from
  push failure in its copy (two distinct message variants sharing this
  layout), and always offers the CSV fallback alongside retry.
- While offline (4.5): Step 2's "Save" button instead shows "Pending —
  will retry when back online," per the resolution at the top of this
  section, and a manual "Retry now" affordance is still available.

### 5.6 Cross-cutting UI notes

- **Reserved gesture space.** Tapping the current card body (not the play
  button, not a swipe) is explicitly a no-op in v1. This is called out so
  it isn't accidentally wired up ad hoc later (e.g. to "show full
  abstract") without a deliberate decision — any such feature should be
  designed and added to this spec first.
- **One primary color-coded action pair.** Green/checkmark = Interested,
  red-or-grey/X = Not interested, used consistently across the swipe
  animation (5.3b), the auto-decide animation, and (for symmetry) the
  Saved List's remove icon reusing the same X glyph as "not interested."
- **Loading states never block gesture input.** Per 5.2's loading state
  and 5.3a's disabled play button, the app prefers disabling the specific
  affected control over showing a full-screen spinner that blocks all
  gestures — consistent with the "fast triage over deep configuration"
  philosophy (1.3).
- **No card is ever pre-rendered more than one ahead** (5.3b), which also
  means narration/TTS pre-fetching (Audio/TTS System section) only needs
  to stay one paper ahead of playback, not the whole queue.

---

## 6. Audio/TTS System

### 6.1 Engine strategy

**v1: the browser's built-in `SpeechSynthesis` API (Web Speech API)** —
Safari, Chrome, Brave, Firefox, and Edge all ship this natively.

**Why this is the right v1 choice:**
- **Zero cost, zero infra.** No TTS server, no per-character API billing,
  no GPU. Fits the "free and open by default" principle (1.3) about as
  hard as possible — the compute is already sitting on the user's device.
- **Zero added latency.** Synthesis happens client-side; there's no
  network round-trip to a TTS backend before a paper can start narrating,
  which matters for the "swipe immediately, no lag" feel (4.6).
- **It's genuinely good enough for the job.** Modern OS voices (macOS/iOS
  Siri voices, Android/Chrome's Google voices, Windows' Neural voices)
  are natural-sounding, not robotic — the "must be good, not just
  technically working" bar you set is realistic with these, unlike older
  robotic engines (e.g. plain eSpeak) which we are explicitly *not* using
  as the v1 default for that reason.
- **It buys time to get the harder part right first** — see 6.4 below.
  Intelligibility of scientific text depends more on *what text you feed
  the engine* than on which engine you use; that work (normalization) is
  needed regardless of engine and carries forward unchanged into v2.

**v2+: self-hosted open-source neural TTS (Piper as the leading
candidate)** — once the core product loop is validated, move to a
self-hosted engine so voice quality and behavior stop depending on the
user's browser/OS. See 6.8 for details and alternatives considered.

This is a deliberate two-stage bet: ship the free, zero-infra option that
is good enough to prove the product, then upgrade the engine once there's
a reason to (consistency across devices, better pronunciation control,
real word-level timestamps) — without having over-invested in TTS infra
before knowing the core swipe/screen loop is worth it.

### 6.2 Web Speech API — behavior and known limitations

| Concern | Reality | Mitigation |
|---|---|---|
| Voice quality varies by OS/browser | Excellent on Chrome/Edge (Google neural voices) and Safari/macOS/iOS (Siri voices); weaker/robotic on some Linux Firefox setups with no system voices installed | Detect available voices at runtime (`speechSynthesis.getVoices()`), prefer known-good voices by name/lang, and surface a clear "your browser has limited voice support" notice rather than silently sounding bad |
| No native SSML support | `SpeechSynthesisUtterance` only exposes `rate`, `pitch`, `volume`, `voice`, `lang` — there is no markup for pauses, emphasis, or phoneme control | Pauses are implemented structurally (6.5), not via markup: narration is split into separate utterances queued with explicit silence gaps in code |
| `onboundary` (word/sentence position) events are inconsistent | Reliable-ish on Chrome/Edge desktop; historically flaky or entirely absent on Safari/iOS and some Android WebViews | Sentence-highlight sync (6.6) never *depends* on boundary events firing — they're used as an optional recalibration signal on top of a timer-based estimate that works everywhere |
| iOS requires a user gesture to start any audio | `speechSynthesis.speak()` must be triggered by a direct tap, or it silently fails | The play button tap *is* that gesture (matches the UI design already — no autoplay is attempted anywhere in the spec) |
| No true offline TTS after first load on some platforms | Most desktop/mobile OS voices work fully offline once the page has loaded, but a few browsers fetch a remote voice model per-utterance | Treat this as a graceful-degradation case under 4.5 (offline mid-session): if speech synthesis fails while offline, fall back automatically to the timer-driven highlight clock described in 6.5 rather than erroring out |

### 6.3 Text normalization pipeline (the actual lever for intelligibility)

This is the highest-leverage v1 investment for the "good, not just
functional" bar, and it is engine-agnostic — it produces plain narration
text that gets fed to whichever engine is active (Web Speech API now,
Piper later), so none of this work is thrown away at the v2 engine swap.

Raw PubMed titles/abstracts are written for *reading*, not *hearing*, and
are dense with constructs that any TTS engine mangles by default:

- **Abbreviations & Latin.** `et al.`, `e.g.`, `i.e.`, `vs.`, `cf.` are
  expanded or corrected to their spoken form (`"et al."` → `"and
  colleagues"`, `"e.g."` → `"for example"`) so they aren't read as
  garbled letter-sounds or mispronounced as words.
- **Statistical & mathematical notation.** `p < 0.05`, `n = 24`, `±`,
  `95% CI`, `r² = 0.8` are rewritten to their spoken equivalents (`"p less
  than 0.05"`, `"n equals 24"`, `"plus or minus"`, `"95 percent
  confidence interval"`).
- **Greek letters & symbols.** `α`, `β`, `Δ`, `μ`, `°C` etc. are expanded
  to their spoken names (`"alpha"`, `"beta"`, `"delta"`, `"micro"`,
  `"degrees Celsius"`) rather than being skipped or read as "unknown
  character" silence.
- **Units and numbers.** Scientific unit shorthand (`mL`, `kg`, `Hz`,
  `nm`) is expanded (`"milliliters"`, `"kilograms"`, `"hertz"`,
  `"nanometers"`); large/decimal numbers are formatted for natural speech
  rather than digit-by-digit reading.
- **Gene, protein, and species names.** These are the hardest category —
  a general-purpose normalizer cannot know every gene symbol. v1 scope is
  intentionally limited: pass these through as-is (most TTS engines at
  least attempt a reasonable phonetic guess for capitalized alphanumeric
  tokens) rather than attempting a comprehensive biomedical dictionary.
  This is flagged explicitly as a known v1 quality gap, not silently
  ignored — a curated biomedical pronunciation dictionary is a natural
  post-v1 improvement once real listening sessions surface which terms
  actually cause problems most often.
- **Sentence boundary cleanup.** PubMed abstracts sometimes contain
  formatting artifacts (stray line breaks, unusual quote characters,
  reference brackets like `[1]`) that read poorly aloud; these are
  stripped or normalized before synthesis, while the *original* text
  (unnormalized) is what's still shown on screen for the highlight, since
  a human reader doesn't need the same cleanup a listener does.

This normalization step runs once per paper when it's fetched into the
queue (not per-playback), producing a "spoken text" version alongside the
original "display text" version — both are needed since 6.6's highlight
sync must map spoken-text timing back onto the original on-screen text.

### 6.4 Narration structure & pause timing

Per the content hierarchy (3.4) and journey (4.1 steps 8-9): title → pause
→ metadata line → pause → abstract. Since Web Speech API has no SSML pause
markup (6.2), this is implemented as separate `SpeechSynthesisUtterance`
objects queued in code, with an explicit silent gap enforced between each
via the `onend` callback of the previous utterance before calling
`.speak()` on the next, rather than relying on punctuation-induced pauses
(which are too short and inconsistent across voices for a clean,
intentional beat).

Two distinct gap lengths are used, not one, to avoid the abstract sounding
like a slideshow of disconnected sentences (see 6.5's note on why a single
gap length for everything is a real intonation/cadence risk):

- **Structural pause (~800ms–1s):** between title → metadata line →
  start of abstract. These are genuine section breaks and should read as
  such.
- **Sentence pause (~150–350ms):** between consecutive sentences *within*
  the abstract — closer to a natural breath/comma-length pause, so
  consecutive sentences still read as one continuous passage rather than
  a list of isolated statements. Exact value is tuned per the active
  Speed setting (faster speed → proportionally shorter gap) during
  implementation/testing, not fixed at one number.

The metadata line itself is assembled from whichever fields the user
enabled in Search & Settings (last author, journal, date — per 3.2.C)
into one short spoken sentence, e.g. *"Smith and colleagues.
Nature Neuroscience. Twenty twenty-five."*

### 6.5 Sentence-highlight sync mechanism, and why splitting is safe

The abstract is pre-split into sentences before playback begins, producing
an ordered list of `(sentenceText, displayCharRange)` pairs. Each sentence
of the *spoken* text is queued as its own `SpeechSynthesisUtterance` (a
natural extension of the per-segment queuing already used for title/
metadata/abstract in 6.4) rather than one giant utterance for the whole
abstract. This gives a reliable, engine-agnostic sync signal for free:
**the currently-playing utterance's index tells the UI exactly which
sentence to highlight** — no dependency on `onboundary` events at all.

**Does splitting into per-sentence utterances hurt intonation?** Not
within a sentence — each utterance is still a complete grammatical unit,
so the engine's normal prosody (clause rises/falls, comma pauses, correct
terminal falling intonation) applies exactly as it would if the whole
abstract were one utterance. The two things that *would* hurt it, and are
addressed directly:

- **Gap length between sentences.** Using the same long structural pause
  (6.4) between every sentence would make the abstract sound disjointed
  regardless of per-sentence prosody being correct — this is why 6.4
  defines a separate, much shorter sentence-pause length specifically for
  this.
- **Sentence tokenizer must be abbreviation-aware, not a naive
  period-split.** A naive `". "` split will incorrectly cut mid-sentence
  on things like `Fig. 2`, `vs.`, `approx.`, `Dr.` that survive the 6.3
  normalization pass — that *would* produce a false terminal fall
  mid-thought, which is the one genuine way splitting can introduce wrong
  intonation. The tokenizer must use a standard abbreviation-exception
  list/library (e.g. the same class of logic as NLTK's Punkt or a
  lightweight JS equivalent) rather than a bare string split, and this
  applies to the *display* text (for correct highlight ranges) and the
  *spoken* text consistently.

- `onboundary` events, where they do fire reliably (6.2), are used only
  as a *bonus* — enabling optional sub-sentence (word-level) highlight
  precision on browsers that support it well, layered on top of the
  sentence-level mechanism, never replacing it.
- **Mute (5.3, 4.2) does not change this mechanism at all.** Muting sets
  `utterance.volume = 0` rather than skipping speech synthesis — the
  engine still synthesizes and still fires `onend`/`onboundary` events on
  the normal schedule, it just produces no audible output. The highlight
  keeps advancing off the exact same utterance-boundary clock whether
  muted or not, which is why there is no separate "silent mode" data path
  to build or maintain (per your steer to drop it in favor of a plain mute
  button).
- **Genuine engine failure is the one case with a different clock.** If
  `speechSynthesis` itself throws or is unavailable (e.g. the offline
  edge case in 4.5, or an unsupported browser), the UI falls back to a
  timer that advances through the same sentence list at an interval
  derived from the Speed setting and each sentence's word count
  (approximating natural reading pace). This fallback exists only for
  "TTS isn't working," never for "the user chose to mute."

**Security note carried into Frontend Architecture (11.3): titles and
abstracts are untrusted external content.** Every string rendered and
highlighted here — title, metadata, abstract, per-sentence spans — comes
from PubMed, a source LitList doesn't control (7.4/7.5). Implementing the
karaoke-style highlight by building an HTML string (e.g. concatenating
`<mark>` tags around the "current" sentence and inserting it via
`dangerouslySetInnerHTML`) would let any HTML/script-like content that
happens to appear in a paper's title or abstract text execute as markup —
a stored-XSS path with an external, uncontrollable input. The highlight
must instead be implemented by rendering the pre-split sentence list as
an array of framework elements (e.g. React `<span>` children with the
"current" one styled), never as raw HTML string interpolation — this is
a hard requirement on the implementation, not a style preference.

### 6.6 End-of-paper cues & mid-narration cancellation

- **End-of-paper chime.** A short, distinct (non-jarring) audio cue plays
  after the last abstract sentence's utterance ends, before the
  auto-decide swipe animation (5.3b) fires. A single shared audio asset,
  not synthesized speech.
- **Muted equivalent.** Per 5.3b, while the mute toggle is on (or if the
  device itself is silenced/unavailable), the same moment is marked with a
  brief visual pulse on the card border instead — the *event* (end of
  paper → auto-decide) is engine-independent; the chime is just its
  audible presentation.
- **Mid-narration swipe cancellation (4.6).** Swiping must call
  `speechSynthesis.cancel()` immediately, which clears the entire
  utterance queue for the current paper (all remaining sentence
  utterances), before the next paper's title utterance is queued. This
  must happen synchronously with the swipe handler so there is no
  audible overlap between papers.

### 6.7 v2+: moving to self-hosted open-source neural TTS

Once the core loop is validated, the plan is to move off browser-default
voices to a **self-hosted, open-source neural TTS engine**, for reasons
distinct from cost (v1 is already free):

- **Consistency.** Every user gets the same voice quality regardless of
  their browser/OS, closing the gap in 6.2's compatibility table.
- **Real timestamps.** Several open-source engines can emit word/phoneme-
  level timing alongside audio, which would let 6.5's highlight sync
  upgrade from "per-sentence utterance boundaries" to genuinely precise
  word-level sync, without changing the product-facing behavior at all —
  just tightening it.
- **Pronunciation control.** Self-hosting opens the door to a proper
  biomedical pronunciation dictionary (the gap flagged in 6.3) via
  engine-level lexicon/phoneme overrides, something the Web Speech API
  gives no control over.

**Leading candidate: [Piper](https://github.com/rhasspy/piper).**
Open-source (MIT), CPU-fast (no GPU required, which matters for staying on
free/cheap hosting tiers per the Deployment section), many permissively-
licensed voices, actively used in production self-hosted contexts (e.g.
Home Assistant). Runs comfortably on the same modest backend that will
already be running the Python API.

**Other open-source engines worth evaluating at that stage** (noted here
so the decision isn't re-researched from scratch later):
- **Kokoro-TTS** — small, fast, Apache-2.0-licensed, newer and well-
  regarded for quality-per-compute; worth a head-to-head against Piper on
  scientific text specifically before committing.
- **Coqui TTS (community fork)** — higher potential quality/expressiveness
  but heavier and less actively maintained since the original company shut
  down; higher hosting cost for a marginal quality gain, so lower priority
  unless Piper/Kokoro prove insufficient.
- **eSpeak-NG** — explicitly *not* a candidate for the primary voice
  (too robotic for the "must be genuinely understandable and pleasant for
  scientific listening" bar), but worth keeping in mind purely as an
  ultra-lightweight offline fallback if a self-hosted neural engine is
  ever unreachable.

This is a *when-we-get-there* decision, not a v1 blocker — v1 ships
entirely on the Web Speech API, and 6.3's normalization pipeline is built
to be engine-agnostic specifically so this migration is a backend swap,
not a rewrite.

---

## 7. PubMed Integration

Source: NCBI's official E-utilities documentation
([NBK25501](https://www.ncbi.nlm.nih.gov/books/NBK25501/) — overview,
[NBK25497](https://www.ncbi.nlm.nih.gov/books/NBK25497/) — parameters/
syntax/policy, [NBK25499](https://www.ncbi.nlm.nih.gov/books/NBK25499/) —
per-utility parameter reference), plus the NIH iCite API for citation
counts (E-utilities has no native citation-count field — see 7.5).

### 7.1 Overall call strategy

Three E-utility calls, each doing only what it's good at, mapped directly
onto what the UI actually needs and when (per 5.6's "never render more
than one card ahead" rule):

1. **ESearch** — turn the user's free-text query into a list of PMIDs
   (PubMed IDs), in the chosen sort order. Cheap, one call per search/
   re-sort.
2. **ESummary** — fetch lightweight metadata (title, journal, date, last
   author, DOI) for the *whole* result page in one batched call. This is
   enough to populate the title-only Next-up preview (5.3) and the
   metadata line (6.4) for every paper in the current batch immediately,
   without waiting on the heavier abstract fetch.
3. **EFetch** — fetch the actual abstract text, one paper (or a small
   look-ahead batch) at a time, just before it's needed for narration —
   this is the one genuinely heavy payload per paper, so it's fetched
   just-in-time rather than for the whole result page up front.

This split means opening the Stack Screen after a search feels instant
(titles are already there from ESummary) while abstract text streams in
just ahead of playback — directly supporting the "fast triage, nothing
blocks the UI" principle from 5.6.

### 7.2 Base URL & endpoints used

All calls go to `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`:

| Utility | Endpoint | Used for |
|---|---|---|
| ESearch | `esearch.fcgi` | Query → ordered list of PMIDs |
| ESummary | `esummary.fcgi` | Batched lightweight metadata per PMID |
| EFetch | `efetch.fcgi` | Full abstract text (structured XML) per PMID |

ELink, EPost, EGQuery, ESpell, ECitMatch, EInfo are not needed for v1 —
flagged here so it's clear they were considered, not overlooked. EPost +
the History server (`WebEnv`/`query_key`) becomes worth adopting if result
sets grow large enough that passing raw PMID lists between calls gets
unwieldy (7.7).

### 7.3 ESearch — building the queue

```
GET esearch.fcgi
  ?db=pubmed
  &term=<url-encoded query>
  &retmax=<page size, default 20, max 10000>
  &retstart=<offset, for pagination>
  &sort=<relevance | pub_date | Author | JournalName>
  &retmode=json
```

Mapping to the Sort control (3.2.C / 5.2):

| UI option | `sort` value | Notes |
|---|---|---|
| Relevance | `relevance` | PubMed's own relevance ranking |
| Recency | `pub_date` | Descending by publication date |
| Citations | *(no native E-utilities value)* | Requires a second data source — see 7.5 |

`term` is the user's raw search text, URL-encoded per NCBI's rules
(spaces → `+`, special characters percent-encoded). No query-building
UI (field-restricted search, MeSH terms, boolean builder) is in v1 scope
— the user's free-text query is sent to PubMed's own query parser as-is,
matching the "simple, fast triage" philosophy (1.3) rather than
replicating PubMed's advanced search UI.

### 7.4 ESummary — populating queue metadata in one batch

```
GET esummary.fcgi
  ?db=pubmed
  &id=<comma-separated PMIDs from ESearch, up to the current page size>
  &retmode=json
```

One call covers the entire current page of results. Relevant fields from
each DocSum, and where they map in the product:

| ESummary field | Used for |
|---|---|
| `title` | Card title (always shown, 3.4) |
| `lastauthor` | Metadata line, if enabled (3.2.C) — PubMed's ESummary conveniently exposes this as its own field, no author-list parsing needed |
| `fulljournalname` / `source` | Metadata line, if enabled |
| `pubdate` / `sortpubdate` | Metadata line (if enabled) and the Recency sort |
| `articleids` (entry with `idtype: "doi"`) | DOI — required later for the Zotero push (Zotero Integration section) |
| `uid` | The PMID itself — primary key used throughout the app's own data model |

ESummary does **not** include the abstract — that's EFetch's job (7.5).
"Country" (mentioned as a possible read-aloud field in the original
product brief, 3.2.C) is **not** a field ESummary or EFetch expose per
article — PubMed only exposes affiliation *strings* per author, which
would require unreliable free-text parsing/heuristics to extract a
country. **Decision: drop "country" from the v1 read-aloud/metadata field
list entirely** rather than ship a low-accuracy guess — Section 3.2.C's
field list should read last author, journal, and publication date only.

### 7.5 EFetch — abstract retrieval

```
GET efetch.fcgi
  ?db=pubmed
  &id=<PMID, or a small look-ahead batch of PMIDs>
  &rettype=abstract
  &retmode=xml
```

`retmode=xml` (not `text`) is the right choice here even though `text`
looks tempting for a "just give me the abstract" use case — the XML
(`PubmedArticleSet` → `PubmedArticle` → `MedlineCitation`) gives
structured, reliably parseable fields (`ArticleTitle`, `AbstractText`,
`AuthorList`, `Journal`, `ArticleDate`) instead of a loosely-formatted
text blob meant for human eyeballs. This matters specifically for 6.3's
normalization pipeline, which needs clean, reliably-delimited input.

**Structured abstracts.** Many biomedical abstracts are broken into
labeled sections (`<AbstractText Label="BACKGROUND">`, `METHODS`,
`RESULTS`, `CONCLUSIONS`, etc.). These labels are preserved and read
aloud as short spoken headers before their section (e.g. *"Background."*
... *"Methods."* ...) — this is genuinely useful structure for rapid
screening, not noise to strip, so it's called out explicitly rather than
being flattened away by the normalization pipeline (6.3).

**Batching.** EFetch supports multiple comma-separated IDs per call, so
the "one paper ahead" pre-fetch (5.6) can, in practice, request the
current + next paper's abstracts in a single call rather than two,
trading a slightly bigger payload for one fewer round trip.

### 7.6 Filling the citation-count gap: NIH iCite API

E-utilities has **no citation-count field** anywhere (not in ESummary,
not in EFetch) — PubMed itself doesn't track citation counts. The
"Sort by citations" option (2.3, 3.2.C) therefore can't be built on
E-utilities alone.

**Recommended source: [NIH iCite](https://icite.od.nih.gov/api)**, run by
the NIH Office of Portfolio Analysis — chosen specifically because it
fits this project's "open-source and free-to-use first" priority (1.3):
free, no API key/auth required, and built from NIH's own Open Citation
Collection rather than a commercial citation index (unlike, say, Scopus
or Web of Science, which are paid and were not considered for that
reason).

```
GET https://icite.od.nih.gov/api/pubs
  ?pmids=<comma-separated PMIDs, batchable — hundreds at a time>
  &fl=pmid,citation_count,relative_citation_ratio
```

- `citation_count` is the field used to power the Citations sort.
- `relative_citation_ratio` (NIH's field-normalized citation metric) is
  noted here as available but **not used in v1** — raw citation count is
  simpler to explain to a user ("more cited" is intuitive; a normalized
  ratio needs a tooltip) and is consistent with 1.3's preference for
  transparent, explainable sort signals over anything that needs
  justifying.
- iCite coverage lags the very newest papers (citation data takes time to
  accumulate) and doesn't cover 100% of PMIDs. UI handling for
  missing/zero citation data on a paper is a Frontend Architecture /
  UI-copy detail (e.g. treat as 0, or show "citation data not yet
  available") to resolve when that section is written — flagged here so
  it isn't forgotten.
- This is a second, independent HTTP dependency beyond NCBI — called out
  explicitly since it adds one more thing that can be slow/down; the
  Citations sort option should degrade gracefully (e.g. fall back to
  Relevance with a brief notice) if iCite is unreachable, rather than
  blocking the whole search.

### 7.7 Rate limits, API key, and required identification

| Without API key | With API key |
|---|---|
| Max 3 requests/second per IP | Max 10 requests/second (higher available on request to NCBI) |

- **Get a free API key** from an NCBI account (ncbi.nlm.nih.gov/account)
  and send it as `api_key` on every E-utilities call. Free, no cost tier,
  matches the project's free/open-source priority — there's no reason not
  to use one from day one.
- **`tool` and `email` parameters**: NCBI asks every E-utilities client to
  send `tool=litlist` and a developer contact `email=` on each request —
  required in practice if an IP ever gets rate-limited/blocked for a
  policy violation, since that's how NCBI identifies and contacts the
  operator. Cheap to include from the start.
- **All E-utilities calls happen server-side** (the Python backend), not
  from the browser — this keeps the API key out of client-side code
  entirely and lets the backend enforce its own request pacing against
  the 10 req/sec ceiling regardless of how many concurrent users LitList
  has, which is a natural fit with the Python-backend-as-proxy
  architecture already decided for this project.
- **Large jobs / bulk use**: NCBI asks that large-scale jobs run on
  weekends or 9pm-5am Eastern on weekdays, and that large-scale abstract
  mining use the downloadable PubMed baseline files instead of
  E-utilities. Not directly relevant to LitList's per-user, on-demand
  query pattern, but worth keeping in mind if a future feature ever did
  bulk pre-fetching across many users' queries.

### 7.8 Compliance

NCBI requires that any product built on E-utilities display NCBI's
disclaimer and copyright notice to end users, and notes PubMed abstracts
may themselves be copyright-protected content licensed for display, not
redistribution. This translates to a concrete v1 requirement: a visible
NCBI attribution/disclaimer notice somewhere in the app (e.g. footer of
the Search & Settings panel, or an About/attribution screen) — exact
placement is a UI Wireframes-level detail to fold back into Section 5 if
needed, but the requirement itself belongs here since it's a condition of
using the API at all.

### 7.9 Error handling & edge cases

- **Zero results** (ESearch returns an empty ID list) → drives the empty
  state in 4.3/5.3a directly; no ESummary/EFetch calls are made.
- **ESearch succeeds but ESummary/EFetch fails for a specific PMID**
  (rare, but PubMed data has occasional malformed/withdrawn records) →
  that paper is skipped from the queue rather than surfacing a broken
  card; not treated as a fatal error for the whole session.
- **Pagination**: `retmax`/`retstart` support fetching beyond the first
  page if a session runs long enough to exhaust the initial batch — the
  backend re-issues ESearch with an incremented `retstart` transparently
  when the user's queue runs low, rather than the user ever seeing a
  "load more" action (keeps with the "fast triage, no manual chores"
  philosophy).
- **Rate-limit errors** (`{"error":"API rate limit exceeded"}`) are a
  backend-only concern given 7.7's server-side proxying — the backend
  should queue/retry with backoff rather than surfacing raw API errors to
  the user.

---

## 8. Zotero Integration

Source: Zotero's official Web API v3 documentation
([Overview](https://www.zotero.org/support/dev/web_api/v3/),
[Basics](https://www.zotero.org/support/dev/web_api/v3/basics),
[Write Requests](https://www.zotero.org/support/dev/web_api/v3/write_requests),
[OAuth](https://www.zotero.org/support/dev/web_api/v3/oauth)).

### 8.1 Library choices and why

- **API base**: `https://api.zotero.org`, all calls server-side from the
  Python backend (never from the browser), for the same reason as
  PubMed (7.7) — keeps credentials off the client and lets the backend
  pace requests against Zotero's rate limits centrally.
- **[Pyzotero](https://github.com/urschrei/pyzotero)** is the recommended
  Python client for the *authenticated read/write calls* (listing
  collections, creating collections, creating items) — it's open-source
  (MIT), actively maintained, and wraps the exact endpoints in 8.4-8.6
  directly, which fits the project's free/open-source-first priority
  (1.3) and avoids hand-rolling JSON payloads for every call.
- **Important gap: Pyzotero does not perform the OAuth handshake itself**
  — it expects you to already have a library ID and API key/token, and
  only wraps calls made *with* those credentials. The OAuth 1.0a dance
  that gets those credentials in the first place (8.2) has to be
  implemented separately, using **`requests-oauthlib`** (also open-source/
  MIT, and already the natural choice for OAuth 1.0a in Python — no other
  library is meaningfully better-suited to this specific, slightly dated
  OAuth version). So the backend has two Zotero-related dependencies:
  `requests-oauthlib` for the one-time login handshake, and `pyzotero`
  for every authenticated call afterward.

### 8.2 Authentication flow (OAuth 1.0a)

Maps directly onto the Screen D1 sub-flow (5.5, Step 1):

1. **One-time setup (developer, not per-user):** register LitList at
   `zotero.org/oauth/apps` to obtain a Client Key and Client Secret.
   Stored as backend secrets (Deployment section).
2. **User taps "Connect to Zotero"** → backend requests a temporary
   request token from `https://www.zotero.org/oauth/request`, then
   redirects the user's browser to `https://www.zotero.org/oauth/authorize`
   with permission parameters (see 8.3 for exactly which ones).
3. **User approves on Zotero's own site** (LitList never sees the user's
   Zotero password — standard OAuth benefit) and is redirected back to a
   LitList callback URL with a verifier.
4. **Backend exchanges the verifier** at
   `https://www.zotero.org/oauth/access` for the final `oauth_token`
   (this token *is* the API key used on all future calls),
   `oauth_token_secret`, and the user's numeric `userID`.
5. **Token is stored** against the user's LitList session/account (Data
   Model section) — per Zotero's docs this token "remains valid
   indefinitely unless revoked by the user," so re-authentication is a
   one-time cost, matching the vision's "authenticate once, be
   remembered" user story (2.3).
6. The app proceeds straight to collection selection (Screen D1 Step 2,
   8.4) — no separate "login success" screen needed.

**Callback redirect must be a fixed path, not attacker-influenceable.**
Step 3's callback URL is the one pre-registered with Zotero in step 1 and
must redirect the user, after completion, to a single fixed in-app path —
never to a URL taken from a query parameter (e.g. a `return_to`/`next`
value). Accepting a dynamic redirect target there would be a textbook
open-redirect vector, letting an attacker craft a LitList OAuth link that
completes real authentication but then bounces the victim to an
attacker-controlled page. Also see 10.2's addendum on binding this whole
handshake to the initiating `session_id`, which addresses a related but
distinct gap (session-fixation, not open-redirect) in the same flow.

### 8.3 Requested permissions (minimal scope)

The authorize-URL parameters double as a permission request. LitList
requests the minimum needed for its actual feature set, rather than the
broadest available scope:

| Parameter | Value | Why |
|---|---|---|
| `library_access` | `1` | Needed to list/write to the user's personal library |
| `write_access` | `1` | Required — pushing saved papers is the entire point of this integration |
| `notes_access` | `0` (omit) | LitList never reads or writes Zotero notes — no reason to request it |
| `all_groups` | omit / `none` | v1 only targets the user's personal library, not shared group libraries (see 8.9 for why this is a deliberate v1 boundary) |

### 8.4 Listing collections (Screen D1, Step 2)

```
GET https://api.zotero.org/users/<userID>/collections
Zotero-API-Key: <oauth_token>
Zotero-API-Version: 3
```

Via pyzotero: `Zotero(userID, 'user', api_key).collections()`. Returns
each collection's `key` (used to file items into it, 8.6) and `name`,
which populates the radio list in the wireframe (5.5). Results are
paginated (`limit`/`start`, default 25 per page per Zotero's docs) —
for the typical researcher's collection count this will usually be a
single page, but the backend should follow the `Link: rel="next"` header
rather than assuming one page.

### 8.5 Creating a new collection ("+ New collection...")

```
POST https://api.zotero.org/users/<userID>/collections
Content-Type: application/json
[{ "name": "<user-entered name>" }]
```

Via pyzotero: `zot.create_collections([{'name': name}])`. The response
includes the new collection's `key`, used immediately for the item push
in 8.6 — this is why 5.5's "+ New collection" expands inline rather than
navigating away: the created collection needs to flow straight into the
same save action.

### 8.6 Pushing saved papers as items

Each saved paper (7.4/7.5's PMID + ESummary/EFetch data) maps to a Zotero
`journalArticle` item:

```json
{
  "itemType": "journalArticle",
  "title": "<ArticleTitle>",
  "creators": [
    {"creatorType": "author", "firstName": "<first>", "lastName": "<last>"}
  ],
  "abstractNote": "<abstract text>",
  "publicationTitle": "<fulljournalname>",
  "date": "<pubdate>",
  "DOI": "<doi, from ArticleIds>",
  "url": "https://doi.org/<doi>",
  "libraryCatalog": "PubMed",
  "extra": "PMID: <pmid>",
  "collections": ["<collection key from 8.4/8.5>"]
}
```

- **Creators**: PubMed's `AuthorList` (from EFetch, 7.5) gives full
  first/last names for every author, which maps cleanly onto Zotero's
  `creators` array — no parsing beyond what EFetch already structures.
- **PMID** has no dedicated Zotero field, so it's placed in `extra`
  (Zotero's documented convention for this kind of supplementary
  identifier) rather than dropped — keeps a traceable link back to the
  PubMed record.
- **Batching**: per Zotero's docs, up to 50 items can be created per
  request. A Saved List (3.5 — capped at one search session, so realistic
  sizes are small, but not bounded in the product) is chunked into
  batches of 50 if it ever exceeds that.
- **Via pyzotero**: `zot.create_items([item_dict, ...])` — pyzotero
  handles the `Content-Type` header and batching mechanics; the backend
  just needs to chunk lists longer than 50 itself.
- **Version headers**: only relevant to *updates* (`PUT`/`PATCH`, which
  require `If-Unmodified-Since-Version`) — since LitList only ever
  *creates* new items and never edits existing Zotero items, this
  requirement doesn't apply to v1's write path at all.

### 8.7 Rate limiting & error handling

Two response headers, handled identically to the PubMed proxy's own
backoff logic (7.9), keeping the backend's retry behavior consistent
across both external APIs:

- **`Backoff: <seconds>`** — sent on any response when Zotero's servers
  are under load; the backend should pause further requests for that
  many seconds even on an otherwise-successful call.
- **`Retry-After: <seconds>`** on `429`/`503` — hard backoff before
  retrying.

Both map directly to the failure states already designed in 4.4/5.5 Step
3b: a failure surfaces the "couldn't save to Zotero" error with retry +
CSV fallback. Because a multi-batch push (8.6) can partially succeed —
e.g. batch 1 of 50 saves, batch 2 fails — the backend must track
per-paper success and report back exactly which papers still need
saving, so a retry (or the CSV fallback) only covers what's actually
missing rather than blindly resubmitting everything and risking
duplicate items for the papers that already saved.

### 8.8 CSV export (no API dependency)

The "Download as CSV" path (Saved List Panel, 5.4) needs no Zotero API
access at all — it's a client-side or backend-generated file from data
LitList already has in-session (PMID, title, authors, journal, date,
DOI). Column set: Title, Authors, Journal, Date, DOI, PMID, URL — chosen
to be importable into other reference managers' CSV import if a user
isn't on Zotero (per the Journal-Club Curator persona, 2.2).

**CSV/formula injection.** Every field here originates from PubMed
metadata (7.4/7.5) — external, uncontrolled text. If any field value
happens to start with `=`, `+`, `-`, or `@` (e.g. an unusual title or an
author-supplied string), spreadsheet applications like Excel or Google
Sheets can interpret it as a formula when the exported file is opened,
which is a known vector (CSV/formula injection) for surprising or
malicious behavior triggered purely by opening a downloaded file. The
generator must neutralize this — prefixing any such field with a leading
single quote (or tab character) before writing it — regardless of how
unlikely a hostile PubMed record is in practice; the cost of the
mitigation is one string check per field, so there's no reason to skip it
on a "probably fine" assumption.

### 8.9 v1 scope boundary: personal library only

LitList v1 only writes to the authenticated user's **personal** Zotero
library, not shared **group** libraries (`all_groups` left unrequested in
8.3). Group-library support is a plausible future addition (e.g. pushing
straight into a shared lab collection) but adds meaningful complexity —
picking which group, handling group-specific permissions — with no
validated demand yet; noted here as a deliberate v1 boundary rather than
an oversight, and a natural Future Roadmap candidate.

---

## 9. Data Model

This section is engine-agnostic (entities, fields, relationships); the
concrete ORM/schema (SQLModel over SQLite, per the project's stack) is
covered in Backend API Specification.

### 9.1 The identity problem this model has to solve

LitList has **no traditional account system** — no signup, no email/
password, no login screen on landing (3.2.A). The only real identity in
the whole product is whatever Zotero's OAuth handshake gives us (8.2), and
even that's optional until the moment of export. But the app still needs
to remember two things across a session (and ideally across visits):
**sticky settings** (3.5 — new searches pre-fill from the last one) and
**in-progress decisions** (so a refresh or backgrounding the PWA mid-
session doesn't wipe the Saved List before it's exported).

**Resolution:** an anonymous, opaque **`session_id`** — a long random
token issued by the backend on first load and stored in the browser
(cookie or PWA local storage), sent on every request. It carries no
personal information and requires no user action to obtain. A Zotero
connection, when made, simply attaches to whichever `session_id` initiated
it. This keeps "no login required" (1.3, 3.2.A) literally true while still
giving the backend something stable to key state against.

**Security property this token has to hold, since it's the only
"credential" in the system.** With no password layer, `session_id` is the
*sole* thing standing between an attacker and a user's in-progress reading
list, settings, and — once connected — their entire Zotero library
(9.6). Two concrete requirements follow directly from that, not just from
general good practice:

- It must be generated with a **cryptographically secure random source**
  (e.g. Python's `secrets.token_urlsafe(32)`, ≥256 bits of entropy) —
  never a sequential ID, a timestamp-based value, or a non-CSPRNG random
  call, any of which would make guessing/enumerating another user's
  session feasible.
- It must be **rotated (reissued) the moment a `ZoteroConnection` is
  created** for a `Session` (8.2 step 5) — i.e. privilege escalation
  (anonymous → Zotero-linked) invalidates the old token and issues a new
  one. This closes a session-fixation path: without rotation, an attacker
  who got a victim to use an attacker-known `session_id` *before* the
  victim connected Zotero would gain access to that Zotero connection
  after the victim connects it, since the identifier never changed across
  the trust boundary.

### 9.2 Entities

**`Session`** — one row per anonymous browser/device, created silently on
first load.
| Field | Notes |
|---|---|
| `session_id` (PK) | Opaque random token, the cookie/localStorage value |
| `created_at` | For retention/cleanup (9.5) |
| `last_seen_at` | Updated on each request; drives cleanup |

**`ZoteroConnection`** — at most one per `Session`, created only once the
user connects (8.2). This *is* the closest thing LitList has to a user
account, and it's entirely optional.
| Field | Notes |
|---|---|
| `session_id` (FK, unique) | One connection per session |
| `zotero_user_id` | From the OAuth access-token exchange (8.2) |
| `oauth_token` | The long-lived API key (8.2) — application-level encrypted, see 9.6 |
| `oauth_token_secret` | Paired secret (8.2) — application-level encrypted, see 9.6 |
| `connected_at` | |

### 9.6 Securing the Zotero OAuth credentials

`oauth_token`/`oauth_token_secret` are bearer credentials for a user's
entire Zotero library with write access (8.3) — if leaked, an attacker
can read and write that library directly. Two concrete mechanisms, not
just a label:

- **Application-level encryption, not "database encryption."** The two
  fields are encrypted before insert / decrypted after read using
  symmetric encryption (Python's `cryptography` library — `Fernet` — free/
  open-source, no new paid dependency) with a dedicated
  `TOKEN_ENCRYPTION_KEY`, kept as its own backend secret (12.3), separate
  from the Turso database credentials. This matters specifically because
  it means a Turso-only leak (backup exposure, credential leak, an
  overly-broad access grant) does **not** by itself expose usable Zotero
  tokens — the attacker would additionally need the encryption key, which
  lives in a different secret store. "Encrypted at rest" as a checkbox
  (e.g. relying solely on the hosting provider's disk-level encryption)
  would not have this property, since disk encryption and database access
  are typically unlocked together.
- **Never sent to the frontend.** Per 8.1/10.5, all Zotero API calls are
  made server-side; the frontend only ever holds LitList's own session
  cookie, never the Zotero token itself. Even a fully compromised
  frontend (XSS, malicious extension) cannot read a credential it's never
  given.
- **Transport**: every hop (browser↔backend, backend↔Zotero, backend↔
  Turso, backend↔PubMed/iCite) is HTTPS/TLS — no leg of any request
  carries these values in plaintext.
- **Revocation**: the user can always revoke LitList's access from
  Zotero's own account settings (standard OAuth behavior, outside
  LitList's control) — and v1 should offer an in-app "Disconnect Zotero"
  action (Saved List Panel, near the export actions, 5.4) that deletes
  the local `ZoteroConnection` row immediately, rather than only ever
  offering the "connect" direction. This was missing from the original
  5.4/5.5 wireframes and should be added there as a small follow-up.
- **CSRF/session-binding gap in the OAuth handshake — see 10.2's addendum**
  for the fix, since it's a backend request-handling concern, not a data-
  storage one.

**`SearchSession`** — the current query + settings for a `Session`. Per
3.5's v1 decision, a new search *replaces* the current one rather than
accumulating a history, so this is naturally a **one-to-one, upsert-in-
place** relationship, not a growing list.
| Field | Notes |
|---|---|
| `session_id` (FK, unique) | |
| `query` | Raw free-text query sent to PubMed (7.3) |
| `sort` | `relevance` \| `recency` \| `citations` (3.2.C, 7.3/7.6) |
| `read_aloud_fields` | JSON: subset of `{last_author, journal, pub_date}` (3.2.C, with "country" dropped per 7.4) |
| `default_swipe_behavior` | `interested` \| `not_interested` (3.2.C) |
| `speed` | Single value driving narration + highlight (6.4/6.5) |
| `updated_at` | Also serves as "last-used settings" for pre-fill (3.5) even before any search has been run this visit |

**`Paper`** — a **global, session-independent cache** of PubMed data, keyed
by PMID. Every user searching overlapping topics shares the same cached
rows — there's no reason to refetch or duplicate PubMed/iCite data per
user, and sharing this cache directly reduces load against the shared
E-utilities/iCite rate limits (7.7/7.6).
| Field | Notes |
|---|---|
| `pmid` (PK) | |
| `title` | |
| `authors` | JSON list of `{first_name, last_name}` (from EFetch `AuthorList`, 7.5 — feeds Zotero `creators`, 8.6) |
| `last_author` | Denormalized from `authors` / ESummary's `lastauthor` (7.4) for fast metadata-line assembly |
| `journal` | ESummary `fulljournalname` (7.4) |
| `pub_date` | ESummary `pubdate` (7.4) |
| `doi` | From `ArticleIds` (7.4/7.5) — required for Zotero push (8.6) |
| `display_abstract` | Original abstract text, with structured section labels preserved (7.5) — what's shown/highlighted on screen |
| `spoken_abstract` | Normalized text for TTS (6.3) — never shown, only spoken |
| `citation_count` | From iCite (7.6); nullable (not all PMIDs are covered) |
| `citation_fetched_at` | iCite data can lag; lets the backend refresh stale counts opportunistically rather than treating them as permanent |
| `esummary_fetched_at` / `efetch_fetched_at` | Cache freshness for the two-stage fetch strategy (7.1) — title/metadata can be cached indefinitely (PubMed records rarely change), abstracts likewise |

**`QueueDecision`** — one row per (search session, paper) pair; this single
table *is* both the live queue state and the Saved List (5.4) — the
Saved List is simply the rows where `decision = interested` for the
current `SearchSession`.
| Field | Notes |
|---|---|
| `session_id` (FK) | |
| `pmid` (FK → Paper) | |
| `position` | Order in the queue (from ESearch's sort order, 7.3) |
| `decision` | `pending` \| `interested` \| `not_interested` |
| `decided_via` | `swipe` \| `auto` \| `manual_remove` (4.1/4.7) — kept mainly for debugging/QA, not surfaced in-product in v1 |
| `decided_at` | |

**`ZoteroExport`** — tracks which decisions have actually been pushed to
Zotero, directly satisfying the partial-batch-failure requirement flagged
in 8.7 (a failed multi-batch push must know exactly which papers still
need retrying, not resubmit everything).
| Field | Notes |
|---|---|
| `session_id` (FK) | |
| `pmid` (FK → Paper) | |
| `zotero_item_key` | The item key Zotero returned on success |
| `zotero_collection_key` | Which collection it was filed into (8.4/8.5) |
| `pushed_at` | |

### 9.3 Relationships

```
Session (1) ──── (0/1) ZoteroConnection
   │
   ├──── (0/1) SearchSession   (replaced on each new search, 3.5)
   │
   └──── (0..N) QueueDecision ──── (N) Paper   (global cache, shared
                    │                           across all sessions)
                    └──── (0/1) ZoteroExport
```

`Paper` is the only entity not scoped to a `Session` — it's shared,
global, cached data. Everything else hangs off the anonymous `Session`.

### 9.4 What is deliberately *not* modeled in v1

- **No cross-`SearchSession` history.** Per 3.5, only the current search
  is kept; there is no `SearchSession` list/table to browse past queries.
  This is why `SearchSession` is one-to-one-with-upsert, not one-to-many.
- **No per-user Zotero collection cache.** Collection lists (8.4) are
  fetched live from Zotero on opening the Saved List Panel rather than
  mirrored locally — they change independently of LitList and are cheap
  to re-fetch, so caching them would just be a staleness risk for no real
  benefit.
- **No analytics/event log entities** in this section — if usage
  analytics are wanted later, that's an additive concern for the
  Deployment/Future Roadmap sections, not a Data Model dependency now.

### 9.5 Retention

Consistent with "no accounts, minimal data" (1.3's "own your data"
principle): `Session`, `SearchSession`, and `QueueDecision` rows for a
device that hasn't been seen in a defined inactivity window (e.g. 30
days — exact value is an ops tuning knob, not a product decision) are
purged. `ZoteroConnection` is the one thing worth keeping longer, since
losing it silently would force an unexpected re-authentication — but
since it's tied to the same `session_id`, if the underlying session is
purged the connection is naturally purged with it; this trade-off (simple
retention story vs. never losing a Zotero connection) should be revisited
if it turns out to matter in practice. The global `Paper` cache is
retention-exempt — it's not personal data and has ongoing value for every
future user.

---

## 10. Backend API Specification

### 10.1 Framework & library choices

| Layer | Choice | Why |
|---|---|---|
| Web framework | **FastAPI** | Async-native (matters for proxying PubMed/iCite/Zotero calls without blocking, 7.1/8.1), free/open-source (MIT), auto-generates OpenAPI docs for free, and is the natural Python counterpart to the async, I/O-bound workload this backend actually does — it's almost entirely "call an external API, reshape the response" |
| ORM / models | **SQLModel** | Also MIT, built specifically to pair with FastAPI — one model definition serves as both the Pydantic request/response schema *and* the SQLAlchemy table definition, which keeps the Data Model entities (Section 9) from having to be defined twice |
| Database | **SQLite** | Zero-infra, file-based, free — fits the "small, free-hosted backend" scale this app runs at (Session/SearchSession/QueueDecision rows are small and short-lived per 9.5; the one larger table, `Paper`, is a simple global cache). A migration path to Postgres exists if scale ever demands it, but isn't needed to ship |
| ASGI server | **Uvicorn** | Standard FastAPI pairing, free/open-source |
| OAuth (Zotero) | **requests-oauthlib** | Per 8.1 |
| Zotero calls | **pyzotero** | Per 8.1 |
| PubMed/iCite calls | Plain `httpx` (async HTTP client) | No dedicated E-utilities Python client is needed — the calls (7.2-7.6) are a handful of well-understood REST GETs; a raw async HTTP client keeps this dependency-light rather than pulling in a heavier PubMed wrapper library for a thin slice of functionality |

Every dependency in this stack is free and open-source — no paid API
tier or proprietary SDK anywhere in the backend, consistent with the
project's stack priority.

### 10.2 Session identity middleware

Implements 9.1's anonymous-session design as FastAPI middleware, not a
per-endpoint concern:

- On any request without a valid `session_id` cookie, the middleware
  creates a new `Session` row, generates an opaque token, and sets it as
  an `HttpOnly`, `Secure`, `SameSite=None` cookie (`SameSite=None` is
  required, not optional, because the frontend and backend are hosted on
  different origins — see Deployment section — so the cookie must be
  usable cross-site).
- Every route handler receives the resolved `Session` (and, if present,
  `ZoteroConnection`) via a FastAPI dependency, rather than re-reading the
  cookie manually in each endpoint.
- No endpoint requires this cookie to be pre-existing — the very first
  request from a brand-new visitor transparently creates one. This is
  what makes "no login screen" (3.2.A) actually true at the API level,
  not just the UI level.

**Cookie consent messaging.** Because this cookie is strictly-necessary
(it holds no tracking/advertising purpose — it only lets the backend
recall an anonymous session's settings and in-progress queue, 9.1) it
likely qualifies for the "strictly necessary" exemption under most
cookie-consent frameworks (e.g. GDPR/ePrivacy) and wouldn't legally
*require* an opt-in banner at all. Regardless of the legal minimum, the
product should still show a brief, honest, one-time notice — not a
generic "we use cookies" banner, but one that says specifically what this
cookie is for, since a vague banner reads as evasive and a precise one
builds trust with a technical audience. Suggested copy, to be finalized
in Frontend Architecture (11) alongside the rest of the app's UI chrome:

> *"LitList uses one cookie to remember your search settings and
> in-progress reading list on this device — no tracking, no ads, nothing
> shared with anyone. If you connect Zotero, the same cookie is what lets
> us remember that connection."*

This ties directly to 1.3's "own your data, own your workflow" principle
— the explanation should make the *actual, narrow* purpose legible rather
than hiding behind boilerplate legal language.

**Binding the OAuth handshake to the initiating session (security fix).**
OAuth 1.0a's request-token step (8.2 steps 2-4) is not, by itself, bound
to any particular LitList session — without an explicit link, nothing
stops the callback in step 4 from being completed by a different browser/
session than the one that started it (e.g. a stale or replayed callback
URL, or a maliciously shared authorize link), which could attach the
wrong `ZoteroConnection` to the wrong `Session`. Fix: when the backend
requests a token in step 2, it stores the pending request token keyed
against the initiating `session_id` (a short-lived row/cache entry, not a
permanent one). On the step-4 callback, the backend verifies that the
request token being completed matches the one it issued *to the session
making this callback request* (i.e. the callback must arrive on the same
session cookie that started the flow) before exchanging it for an access
token — rejecting the callback otherwise. This is a small, cheap check
that closes a real session-fixation-style gap rather than trusting the
OAuth provider's redirect alone to guarantee who's on the other end.
### 10.3 Conventions

- Base path: `/api/v1/...` — versioned from day one since this spec will
  evolve (Future Roadmap), even though only one version will ever exist
  at v1 launch.
- Errors: a consistent JSON shape — `{"error": {"code": "...",
  "message": "..."}}` — rather than ad hoc per-endpoint error bodies, so
  the frontend has one error-handling code path (Frontend Architecture
  section) instead of one per endpoint. `message` must always be a safe,
  pre-written string keyed off `code` — never the raw exception text or a
  stack trace. Leaking internal exception details (file paths, query
  fragments, library internals) in an API error response is a common way
  to hand an attacker a map of the backend for free; full exception
  details are logged server-side (12.6) for debugging, never returned to
  the client.
- Pagination (where relevant, e.g. `/search`): `limit`/`offset` query
  params mirroring the underlying ESearch `retmax`/`retstart` (7.3) —
  deliberately reusing the same mental model rather than inventing a
  different pagination convention at the LitList API layer.

### 10.4 Endpoints

| Method & path | Purpose | Notes |
|---|---|---|
| `POST /api/v1/search` | Run a new search: body `{query, sort, read_aloud_fields, default_swipe_behavior, speed}` | Upserts the session's `SearchSession` (9.2, replacing any prior one per 3.5), calls ESearch + batched ESummary (7.3/7.4) + iCite (7.6) for the first page, creates `QueueDecision` rows (`pending`), returns the queue (title/metadata only — no abstracts yet, per 7.1's two-stage strategy) |
| `GET /api/v1/search/settings` | Return the current session's last-used settings | Powers the pre-fill behavior (3.5) even before any search is run this visit |
| `GET /api/v1/queue` | Return the current `SearchSession`'s queue (papers + decisions), paginated | Backend transparently issues a follow-up ESearch page (with incremented `retstart`) when the queue is running low, per 7.9 — the client never has to ask for "more" explicitly |
| `GET /api/v1/papers/{pmid}/abstract` | Fetch (or serve cached) `display_abstract` + `spoken_abstract`, pre-segmented into sentences (6.5) | Called by the frontend for the *current* and *next-up* paper only, per 5.6's one-ahead rule — this endpoint is the concrete implementation of that rule, not a bulk abstract endpoint |
| `PATCH /api/v1/decisions/{pmid}` | Body `{decision, decided_via}` | Updates a `QueueDecision` row (4.1, 4.6, 4.7) |
| `GET /api/v1/saved` | List saved papers for the current session (`QueueDecision.decision == interested`, joined with `Paper`) | Backs the Saved List Panel (5.4) |
| `DELETE /api/v1/saved/{pmid}` | Undo/remove from the saved list | Sets the decision back to `not_interested` rather than deleting the row outright, preserving the audit trail described in 9.2 (4.7 — this does not resurrect the card in the live queue) |
| `GET /api/v1/zotero/auth/start` | Begins the OAuth handshake (8.2 step 2), redirects to Zotero | |
| `GET /api/v1/zotero/auth/callback` | OAuth callback (8.2 step 4) | Stores the `ZoteroConnection`, redirects back into the app |
| `GET /api/v1/zotero/collections` | List the connected user's collections (8.4) | 401-equivalent app error if no `ZoteroConnection` exists yet, which the frontend uses to trigger the "Connect to Zotero" step (5.5) |
| `POST /api/v1/zotero/collections` | Create a new collection (8.5) | Body `{name}` |
| `POST /api/v1/zotero/push` | Body `{collection_key, pmids: [...]}` | Batches into groups of 50 (8.6), writes `ZoteroExport` rows per success, returns a per-PMID success/failure list — never an all-or-nothing result, per 8.7 |
| `GET /api/v1/export.csv` | Streams the CSV export (8.8) | No Zotero dependency; works even without a `ZoteroConnection` |

### 10.5 Outbound rate-limit governance

Three external APIs (PubMed E-utilities, iCite, Zotero) each have their
own rate limits (7.6/7.7/8.7) that apply **per backend, across all
concurrent LitList users** — not per user. This means rate-limit handling
belongs in one shared place, not duplicated per endpoint:

- A single outbound-request layer per external service (three thin
  wrapper clients: `pubmed_client`, `icite_client`, `zotero_client`) is
  the only code allowed to make the actual HTTP calls — no endpoint talks
  to an external API directly.
- Each wrapper enforces its own pacing (e.g. a simple async semaphore/
  token-bucket sized to the documented ceiling — 10 req/sec for PubMed
  with an API key, per 7.7) and honors `Backoff`/`Retry-After` response
  headers (7.7/8.7) by pausing *all* outbound calls of that type, not
  just the one that received the header.
- This is a natural chokepoint for the `Paper` cache (9.2) too — the
  PubMed/iCite wrappers check the cache before making a network call at
  all, which is both a performance win and directly reduces how often the
  rate limit is even approached.

**This governs outbound traffic, not inbound abuse — a separate,
additional control is needed.** Because there's no login/accountability
layer (9.1), nothing stops a single client from calling LitList's own
`/api/v1/search` (or the abstract/push endpoints) in a tight loop. Two
distinct problems follow from that, and outbound pacing alone doesn't
solve either:
- **Shared-budget exhaustion**: one abusive client can consume the entire
  10 req/sec PubMed allowance (which is shared across *every* concurrent
  LitList user, 7.7) before anyone else's request gets a turn.
- **Using LitList as a free, unauthenticated PubMed/Zotero-writing proxy**
  — since the backend holds the NCBI API key and, once connected, a
  user's Zotero write credential, an attacker script hitting these
  endpoints directly (bypassing the actual UI) gets amplified access to
  both.

**Fix: per-`session_id` (and, as a backstop, per-IP) request throttling
at the LitList API layer itself**, independent of and in addition to
10.5's outbound governance — e.g. a request-per-minute cap on `/search`,
`/papers/{pmid}/abstract`, and `/zotero/push` enforced before a request
is even allowed to reach the outbound wrappers. This is a standard
FastAPI middleware concern (e.g. `slowapi`, free/open-source) rather than
new infrastructure.

### 10.6 No real-time/streaming layer needed

The one-ahead prefetch pattern (5.6, 6.5, 10.4's abstract endpoint) is
satisfiable entirely with plain request/response calls timed by the
frontend (fetch the next-up paper's abstract as soon as the current one
starts playing) — there's no case in this product where the backend needs
to push data to the client unprompted. This is called out explicitly so a
WebSocket/SSE layer isn't accidentally reached for later without a
concrete reason: it would add real operational complexity (connection
lifecycle, reconnection handling) for a product that has no genuine
real-time requirement in v1.

Similarly, no background task queue (e.g. Celery + Redis) is needed for
v1 — the only "background-ish" work is opportunistic citation-count
refresh (9.2's `citation_fetched_at` staleness) and Zotero backoff
pausing, both of which fit comfortably in FastAPI's built-in
`BackgroundTasks` or a simple in-process scheduled job, matching the
original architecture sketch's "Redis (optional later)" — later, not now.

### 10.7 CORS

The frontend (static PWA, Deployment section) and backend are hosted on
different origins by design (free static hosting for the frontend, a
small always-on process for the backend — see Deployment). FastAPI's
CORS middleware is configured with an explicit allow-list of the
frontend's real origin(s) plus `allow_credentials=True` (required for the
session cookie in 10.2 to be sent cross-origin) — never a wildcard
origin, since wildcard + credentials is both disallowed by browsers and a
real security footgun.

**This strict allow-list is also LitList's main CSRF defense, not just a
cross-origin-fetch convenience — worth stating explicitly so it isn't
weakened by accident later.** `SameSite=None` (10.2) is required for the
cookie to work cross-origin, but it also disables the CSRF protection
`SameSite=Lax`/`Strict` would otherwise give for free — meaning cookie
auth alone, on its own, would let any site the victim visits trigger
authenticated requests against LitList's API. What actually prevents this
here: every state-changing endpoint (`PATCH /decisions`, `POST /zotero/
push`, etc.) requires a `Content-Type: application/json` body, which is a
non-"simple" request under the CORS spec and therefore triggers a
preflight `OPTIONS` check — a request from a non-allow-listed origin
never reaches the route handler at all. **This protection depends
entirely on every state-changing endpoint continuing to require a JSON
body and the origin allow-list staying strict** — adding a form-
compatible (`multipart/form-data` or default-encoded) endpoint, or
loosening the allow-list, would silently reopen CSRF. Worth a standing
test/lint rule rather than relying on this being remembered.

**Baseline security response headers** (`X-Content-Type-Options: nosniff`,
a conservative `Content-Security-Policy`, `Referrer-Policy`) should be set
on every backend response as a second, independent layer of defense
alongside 6.5/11.3's rendering-level XSS mitigation — cheap to add via
FastAPI middleware and standard practice, not specific to anything
unusual about this app.

### 10.8 Explicitly out of scope for v1

- No admin/internal API surface (no need identified yet).
- No public API for third parties — this API exists to serve LitList's
  own frontend, not as a product in itself.
- No auth beyond the Zotero-connection model in 9.1/10.2 — no separate
  LitList username/password layer is ever introduced.

---

## 11. Frontend Architecture

### 11.1 Framework & library choices

| Layer | Choice | Why |
|---|---|---|
| Framework | **React + TypeScript, via Vite** | Free/open-source, huge ecosystem for the PWA/gesture/animation needs below, and Vite's dev server + build are fast and free — no paid tooling anywhere in the build chain |
| Styling | **TailwindCSS** | Free/open-source; fits a UI that's mostly a handful of well-defined screens (Section 5) rather than a large design system — utility classes avoid maintaining a separate CSS architecture for something this scoped |
| Server state | **TanStack Query** | Wraps the Section 10 endpoints (search, queue, saved, zotero collections) with caching, refetch, and loading/error states out of the box — maps naturally onto a backend that's mostly "fetch and cache" (10.4, `Paper` cache in 9.2) |
| Local/client-only state | **Zustand** | For state that has no backend counterpart at all (11.2) — lightweight, free/open-source, avoids Redux-level boilerplate for a app with a genuinely small local-state surface |
| Swipe/animation | **Framer Motion** | Implements the drag-to-decide gesture and the swipe-away/slide-in animations specified in 5.3b; free/open-source, and its drag gesture primitives are a direct fit for "swipe past a threshold = decide" |
| PWA/offline shell | **`vite-plugin-pwa`** | Free/open-source Vite plugin generating the service worker + manifest needed for "Add to Home Screen" (11.5) |

Every layer here is free/open-source, consistent with the backend (10.1)
and the project's overall stack priority — there is no paid service or
proprietary SDK anywhere in the frontend either.

### 11.2 State architecture: what lives where

The single most common source of frontend bugs in an app like this is
letting the same fact live in two places (e.g. "is this paper saved?"
tracked separately in a local array *and* the server). This is avoided by
drawing one hard line:

**Server state (TanStack Query, source of truth = backend):**
- The current queue and its decisions (`GET /queue`, `PATCH /decisions/
  {pmid}`)
- The saved list (`GET /saved`)
- Search settings pre-fill (`GET /search/settings`)
- Zotero collections (`GET /zotero/collections`) and connection status
- A swipe optimistically updates the local TanStack Query cache
  immediately (so the animation in 5.3b never waits on a network
  round-trip) and reconciles with the server response in the background —
  matching the "fast triage, nothing blocks the UI" principle (5.6).

**Local-only state (Zustand, no backend counterpart, ever):**
- Whether narration is currently playing/paused (6.4-6.6's playback
  engine state)
- The mute toggle (Section 6's mute mechanism — this is purely a client-
  side `utterance.volume` setting, 6.5, so it has no reason to touch the
  backend at all)
- The currently-highlighted sentence index (6.5)
- In-progress (unsaved) edits to the Search & Settings panel before the
  user taps "Start" (5.2) — only committed to the backend (and thus to
  TanStack Query) once a search actually runs
- UI-only state: which panel is open (Search & Settings / Stack / Saved
  List, per the navigation model in 3.3), whether the cookie-consent
  notice (10.2) has been dismissed this session

### 11.3 The playback engine as one isolated module

Section 6's mechanics (per-sentence utterance queuing, the two pause
lengths, mute-via-volume, the timer-based fallback clock, boundary-event
handling, cancellation on swipe) are substantial enough that they must
live in **one dedicated module** (e.g. a `usePlaybackEngine` hook) rather
than being spread across UI components. This module:

- Owns the `SpeechSynthesisUtterance` queue and the fallback timer (6.5)
  as private internal state — components never touch
  `speechSynthesis` directly.
- Exposes a small action surface to the UI: `play()`, `pause()`,
  `toggleMute()`, and fires callbacks/state updates for "sentence N is
  now highlighted" and "paper finished" (which the Stack Screen
  component uses to trigger the auto-decide animation, 5.3b).
- Consumes `display_abstract`/`spoken_abstract` from the TanStack Query
  cache for the current and next-up paper (10.4's one-ahead abstract
  endpoint) — it doesn't fetch data itself, it's handed already-cached
  data and turns it into audio + highlight events.
- Is the single place `speechSynthesis.cancel()` gets called (4.6), so
  mid-narration swipe cancellation can't be implemented inconsistently
  in one screen vs. another.

Isolating this avoids the realistic failure mode where two different
components each hold a slightly different idea of "what's currently
playing."

This module emits *data* (which sentence index is current), never
markup — the component that renders the highlighted abstract consumes
that index to style one `<span>` among plain-rendered sentence elements.
Per 6.5's security note, it must never construct an HTML string from
paper text and inject it — title/abstract content is untrusted external
data (from PubMed), and framework-level auto-escaping is the whole
defense against it becoming a stored-XSS vector.

### 11.4 Swipe/decision handling

Framer Motion's drag gestures (11.1) power the current card (5.3): a
drag past a horizontal threshold triggers the same code path as a
programmatic auto-decide (5.3b, 4.1 step 10) — swipe and auto-decide are
two triggers into **one** decision function, not two separate
implementations, so the animation, backend call (`PATCH /decisions/
{pmid}`), and next-card prefetch (triggering the abstract fetch for the
new next-up paper, 10.4) always happen consistently regardless of which
triggered the decision.

### 11.5 PWA & offline behavior

- `vite-plugin-pwa` generates the manifest (name, icons, theme color) and
  a service worker that precaches the app shell (JS/CSS/static assets) —
  this is what makes "Add to Home Screen" and instant reloads work.
- **What is *not* cached by the service worker**: PubMed/paper data. That
  already has a server-side cache (`Paper`, 9.2); duplicating it
  client-side in the service worker would just create a second cache to
  keep consistent for no benefit.
- **What *is* kept available offline mid-session (4.5)**: TanStack
  Query's in-memory cache already holds whatever's been fetched so far
  (current queue, current + next-up abstracts) — a connectivity drop
  doesn't clear this, so playback of already-loaded papers continues
  uninterrupted per 4.5's edge case, with no extra persistence layer
  needed beyond what TanStack Query already does in memory.
- New network requests (new search, further pagination, Zotero push)
  naturally fail while offline and surface through the shared error
  handling (11.7) as the "pending — will retry" states already specified
  in 4.5/5.5.

### 11.6 Routing

The IA (Section 3) is fundamentally one screen with panels toggled by
gesture/UI state (3.3) — not a set of distinct pages — so a full router
(React Router or similar) is unnecessary complexity for v1. The **one**
exception is the Zotero OAuth callback (8.2 step 3-4), which genuinely
needs a real URL for Zotero to redirect back to; this is handled as a
single dedicated route that processes the callback and then hands off
into the same single-page app state, rather than justifying a router for
the whole application.

### 11.7 Error handling & the cookie-consent notice

- TanStack Query's error states are handled through one shared component
  (matching the backend's consistent `{"error": {...}}` shape, 10.3) so
  every failure mode (search failure, abstract fetch failure, Zotero
  push failure, offline) renders through the same mechanism, specialized
  per-context only in *copy*, not in plumbing — directly implementing the
  distinct error states already designed in 4.3/4.4/4.5/5.3a/5.5.
- The cookie-consent notice specified in 10.2 is a simple, dismiss-once
  banner — its dismissal is tracked in Zustand/local UI state (11.2), not
  as a gate on any functionality, since the underlying cookie is
  strictly-necessary and already set regardless (10.2). The banner is
  purely about being upfront, not about blocking access pending consent.

---

## 12. Deployment & CI

### 12.1 A real constraint this section had to resolve first

The obvious free choice for the backend host — **Render's free web
service tier** — turns out to conflict with the data model as designed.
Render's own docs confirm free web services have an **ephemeral
filesystem: any local file, including a local SQLite database, is wiped
on every redeploy, restart, *or* spin-down (which happens automatically
after ~15 minutes of inactivity)**. Since Section 9 deliberately wants
`ZoteroConnection` to survive across a user's return visits days or weeks
apart (9.5), a SQLite file sitting on Render's free-tier local disk would
silently lose exactly the data most worth keeping. This is the kind of
thing worth checking against current provider docs rather than assuming
"free tier + SQLite" just works — it doesn't, on Render specifically.

**Resolution:** keep Render (or an equivalent) for free compute, but move
the actual database off local disk onto **[Turso](https://turso.tech)** —
a free-tier-forever, SQLite-compatible hosted database (built on
`libSQL`, an open-source SQLite fork). This is close to a drop-in swap for
the SQLModel/SQLite choice already made in Section 10 (same SQL dialect,
different connection string via the `sqlalchemy-libsql` driver), and it's
the one piece of this stack that isn't itself open-source (it's a hosted
service, like Render or GitHub Pages) — flagged explicitly since it's the
exception to 10.1/11.1's all-open-source dependency list, justified here
purely because it solves a real persistence problem for free.

### 12.2 Hosting choices

| Component | Choice | Why |
|---|---|---|
| Frontend (static PWA build) | **GitHub Pages** or **Cloudflare Pages** | Both free forever, no cold starts (pure static hosting), free custom domain + HTTPS. Either works; Cloudflare Pages has a slight edge (faster global CDN, more generous build minutes) but GitHub Pages needs zero extra account setup if the repo is already on GitHub — a reasonable default, upgradeable to Cloudflare Pages later with no code changes since it's just static files |
| Backend compute | **Render (free web service)** | Free, git-push-to-deploy simplicity, free HTTPS. Trade-off accepted explicitly in 12.4 |
| Database | **Turso** (per 12.1) | Free tier, SQLite-compatible, actually persistent |
| Secrets | Platform-native env var storage (Render's dashboard secrets, GitHub Actions secrets for CI) | Never committed to the repo — see 12.3 |

### 12.3 Environment & secrets

The backend needs these secrets, injected as environment variables by
Render's dashboard (never committed to the repo, never in a `.env` file
that gets pushed):

- `NCBI_API_KEY`, `NCBI_TOOL`, `NCBI_EMAIL` (7.7)
- `ZOTERO_CLIENT_KEY`, `ZOTERO_CLIENT_SECRET` (8.2)
- `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` (12.1)
- `SESSION_COOKIE_SECRET` (used to sign the session cookie, 10.2)
- `TOKEN_ENCRYPTION_KEY` (encrypts `ZoteroConnection.oauth_token`/
  `oauth_token_secret` at the application level, 9.6) — this is the one
  most worth double-checking never ends up alongside the database
  credentials it's meant to be independent of (9.6's whole point is that
  a Turso-only leak shouldn't be enough to decrypt tokens)

GitHub Actions (12.4) gets its own scoped secrets (e.g. a Render deploy
hook URL) via repository secrets — kept separate from the runtime
backend secrets above. The `TURSO_AUTH_TOKEN` itself should be scoped
(least privilege) to only the LitList database if Turso's token scoping
supports it, rather than an account-wide token — limits the blast radius
if this specific secret ever leaks.

### 12.4 CI/CD via GitHub Actions

Two independent workflows, since the frontend and backend deploy to
different places on different triggers:

- **On every pull request**: lint + typecheck (frontend: `tsc`/ESLint;
  backend: `ruff`/`mypy`) + test suite for both, blocking merge on
  failure. No deploy happens here.
- **Dependency vulnerability scanning**: GitHub's Dependabot (free,
  built into any GitHub repo — no new tooling to adopt) enabled for both
  `package.json` (frontend) and `requirements`/`pyproject.toml`
  (backend), opening PRs for known-vulnerable dependency versions. Worth
  calling out specifically here since this stack (10.1/11.1) leans
  heavily on third-party open-source packages (FastAPI, pyzotero,
  requests-oauthlib, React ecosystem libs) precisely because they're free
  — free/open-source is the right default, but it means supply-chain
  hygiene has to be someone's/something's job rather than assumed away.
- **On merge to `main`**:
  - Frontend: build the Vite app, publish the `dist/` output to GitHub
    Pages (or Cloudflare Pages, via their respective official GitHub
    Actions).
  - Backend: Render's native git-integration auto-deploys on push to
    `main` directly (no GitHub Action needed for this leg) — simpler than
    routing the backend deploy through Actions when Render already
    watches the repo itself.

This is intentionally lightweight — no staging environment, no manual
approval gate — matching the scale of a free, single-maintainer v1
product; a staging environment is a reasonable thing to add later if
the contributor base grows, not a v1 requirement.

### 12.5 Accepting the cold-start trade-off

Render's free web service spins down after ~15 minutes idle and takes
roughly a minute to wake on the next request. This is an explicit,
accepted trade-off for v1 rather than something to engineer around (e.g.
a scheduled "keep-alive" ping) — LitList's actual usage pattern (an
occasional screening session, not an app needing sub-second cold opens)
tolerates a one-time minute-long wait on a cold start far better than it
would tolerate paying for always-on compute before the product has any
validated usage. If cold starts prove to be a real adoption blocker once
there are actual users, upgrading Render to its cheapest always-on paid
tier is a two-click change, not a re-architecture — noted here as the
upgrade path rather than something to pre-optimize for now.

### 12.6 Monitoring & backups

- **Logs**: Render's built-in log viewer (free, included) is sufficient
  for v1 — no separate observability service (e.g. Datadog, Sentry) is
  justified yet at this scale; adding error tracking is a reasonable
  Future Roadmap item once there's real usage to observe. This is also
  where 10.3's full exception details land (server-side stdout/stderr,
  captured by Render) — never in the API response itself.
- **Backups**: Turso includes point-in-time recovery on its free tier,
  which covers the `ZoteroConnection`/`Session` data worth protecting
  (9.5). The global `Paper` cache (9.2) needs no backup story at all —
  it's fully reconstructible from PubMed/iCite on demand, so losing it is
  a performance blip, not a data-loss event.

---

## 13. Accessibility & Edge Cases

### 13.1 Gesture-only interaction excludes real users — needs tap/keyboard parity

The core interaction (Section 3/5) is built around swipe gestures, but
swipe-only interaction excludes anyone using a mouse/trackpad on desktop
(the vision explicitly targets "any device," 1.1), anyone with a motor
impairment that makes a drag gesture difficult or impossible, and anyone
navigating via screen reader (where "swipe" as a raw drag isn't how
screen-reader users interact with content at all). This isn't purely an
accessibility nicety — for a desktop/laptop PWA user there's no
"swipe" without it, so a tap/click/keyboard equivalent is a **functional
requirement**, not an enhancement:

- **Every swipe has a tap/click equivalent.** The Stack Screen (5.3)
  needs explicit "Interested" / "Not interested" buttons alongside the
  swipeable card (not just the play button) — this was a gap in the
  original wireframe, which only gave the Search & Settings panel a
  tap-alternative ("Start" button, 5.2) but left the actual decision
  gesture swipe-only. Fixed here: add two small buttons (or icons) flanking
  or below the current card, functionally identical to a left/right
  swipe, wired to the same single decision function (11.4) so behavior
  never diverges by input method.
- **Keyboard shortcuts** for desktop use: Space = play/pause, Left/Right
  arrow = not-interested/interested, Up/Down arrow = open/close the
  Saved List and Search & Settings panels (mirroring the swipe-up/down
  model in 3.3). Standard, discoverable (e.g. a small "?" shortcuts
  reference), and means a desktop user is never forced to fight a
  touch-first interaction model with a mouse.
- **Screen reader support**: every icon-only control (play/pause, mute,
  the tap-decision buttons above) needs an `aria-label`; state changes
  that are currently communicated only visually or audibly — "now
  playing: `<title>`," a paper being marked interested/skipped, the
  end-of-paper chime — need an `aria-live` region announcement, since a
  screen-reader user gets neither the visual swipe animation nor
  necessarily the audio chime cues in a way their screen reader surfaces
  automatically.
- **Color is never the only signal.** The green/red interested/not-
  interested coding (5.6) already pairs color with a checkmark/X icon —
  this pairing is a hard requirement (not just the current choice) so
  colorblind users aren't relying on hue alone; both colors must also meet
  WCAG AA contrast ratios against their backgrounds.
- **Respect `prefers-reduced-motion`.** The swipe-away arc animations
  (5.3b) should collapse to a simple cross-fade for users who've set this
  OS-level preference — relevant given some users have vestibular
  disorders that make sustained motion/parallax genuinely uncomfortable,
  not just a preference.
- **Mute mode already doubles as a deaf/hard-of-hearing accommodation.**
  Worth naming explicitly: the mute + text-highlight mechanism built for
  the no-earphones use case (2.3, 6.5) is the same mechanism that makes
  the app fully usable for a deaf or hard-of-hearing researcher — no
  separate accessibility feature needed here, just worth recognizing the
  overlap so it isn't accidentally treated as a lesser/secondary path in
  implementation.

### 13.2 The most important limitation: background/lock-screen audio

**This directly affects the core vision** ("listen while walking,
commuting, phone in pocket," 1.1) and needs to be stated plainly rather
than discovered late: the Web Speech API generally **does not reliably
keep speaking once the browser tab is backgrounded or the phone's screen
locks**, across most mobile browsers. Unlike a native `<audio>`/`<video>`
element paired with the Media Session API (which OSes are built to keep
alive for exactly this "phone in pocket, screen off" scenario), raw
`speechSynthesis` calls are JS-driven and are commonly throttled or
suspended by the OS/browser the moment the tab loses foreground focus —
this is a real, current limitation of the v1 engine choice (6.1), not a
hypothetical edge case.

**v1 mitigation (partial, not a full fix):**
- Use the **Screen Wake Lock API** (a standard, free web API, no library
  needed) to keep the screen from auto-locking while narration is
  playing — this at least keeps the common "phone in hand, screen would
  otherwise dim/lock" case working.
- Be upfront in the product copy (e.g. a first-run tip) that LitList
  needs to **stay open and the screen on** to keep narrating — setting
  the right expectation is better than a user discovering silent playback
  failure mid-walk with no explanation.
- The mute + on-screen highlight path (6.5) still requires the screen on
  too (it's visual), so this limitation isn't specific to audio mode —
  it's really "the tab must stay foregrounded," full stop, for v1.

**v2 path (ties to 6.7):** once self-hosted neural TTS (Piper/Kokoro)
produces actual pre-rendered audio *files* rather than live
browser-synthesized speech, narration can be played through a real
`<audio>` element wired to the Media Session API — which *does* support
lock-screen/background playback properly (media controls on the lock
screen, continues playing with the screen off) — the same engine upgrade
already planned for voice-quality reasons (6.7) also happens to be what
fixes this. Worth having in mind when 6.7 is eventually scheduled, since
it reframes that migration as fixing a real functional gap, not just a
quality upgrade.

### 13.3 Non-English or mixed-script abstracts

PubMed indexes some non-English-language papers (with or without an
English abstract translation). The Web Speech API's chosen voice (6.2)
is generally locked to one language; feeding it non-English or
mixed-script text produces poor-to-unusable narration (wrong phonemes,
or silence on unrecognized scripts). v1 handling: detect a language
mismatch between the abstract's actual language and the active narration
voice (PubMed's `Language` field on the record, when present, makes this
cheap rather than requiring real language detection) and, when mismatched,
skip audio narration for that paper specifically while still showing the
text on screen with a brief note ("Narration unavailable for this
language") — degrading gracefully rather than mangling the audio or
silently skipping the paper from the queue entirely.

### 13.4 PubMed data edge cases

- **Missing DOI.** Older PubMed records often lack a DOI. The Zotero item
  payload (8.6) simply omits the `DOI`/`url` fields when absent — Zotero
  treats all fields but `itemType`/`tags`/`collections`/`relations` as
  optional, so this isn't a failure case, just an incomplete-but-valid
  item. The CSV export (8.8) leaves that column blank for the same
  papers rather than erroring.
- **Retracted papers / errata.** PubMed marks some records with
  publication types like "Retracted Publication" or links a correction
  notice. This is a genuinely useful screening signal, not just a data
  quirk — worth surfacing in the metadata line or as a visible badge on
  the card ("⚠ Retracted") when present, rather than silently narrating a
  retracted paper's abstract as if it were live science. Flagged here as
  a small, worthwhile v1 addition rather than deferred to the roadmap,
  since the underlying data (`PublicationType`) is already present in the
  EFetch payload (7.5) at no extra fetch cost.
- **Unusually long abstracts** (e.g. structured Cochrane systematic
  review summaries running far longer than a typical abstract) simply
  take longer to narrate — no special handling required, since the
  per-sentence queuing (6.5) and mid-narration swipe (4.6) already handle
  "the user gets impatient and swipes before the end" gracefully
  regardless of length.

### 13.5 Multiple tabs / devices on the same anonymous session

Because identity is a browser-stored `session_id` (9.1), opening LitList
in two tabs (or two devices sharing a copied session cookie, unusual but
possible) means both would read/write the same `SearchSession` and
`QueueDecision` state with no coordination between them (10.6 already
ruled out a real-time sync layer for v1). **This is an explicit v1
non-goal, not an oversight**: the backend behaves correctly for any
single request (last-write-wins), but two tabs actively driving the same
session simultaneously can produce a confusing interleaved experience
(e.g. both auto-advancing independently). Worth a light mitigation —
detecting a second active tab and showing a passive notice — but full
multi-tab session sync is a Future Roadmap-tier concern, not a v1
requirement, given how narrow the scenario is.

### 13.6 External dependency downtime (as opposed to user-side offline)

Section 4.5 covers *the user's own* connectivity dropping. A distinct
case: PubMed, iCite, or Zotero themselves being slow/down while the
user's own connection is fine. This should degrade the same way a
rate-limit backoff does (7.9/8.7) — a clear "PubMed is currently
unavailable, try again shortly" state rather than a generic error or an
indefinite spinner — and, per 9.2, any already-cached `Paper` data keeps
serving normally throughout, since the global cache doesn't depend on
PubMed being reachable *right now* to answer requests for data it
already has.

### 13.7 No Web Speech API support at all

A small number of browsers/embedded webviews have no `speechSynthesis`
support whatsoever (distinct from 6.2's "it exists but `onboundary` is
flaky" cases). This is the same fallback path already designed for
offline/engine-failure (6.5's timer-driven clock) — it applies identically
whether the API is missing entirely or merely throws at runtime. The one
addition needed here is a one-time, non-blocking UI notice ("Audio
narration isn't available in this browser — you can still read along")
so the absence of sound reads as an explained limitation rather than a
silent bug.

---

## 14. Future Roadmap

Everything below was deliberately scoped out of v1 elsewhere in this
document, with reasoning given at the time. This section exists so those
decisions are visible in one place — as a roadmap, not as a list of
things v1 forgot.

### 14.1 Personalization

- **Recommendation engine** (explicitly ruled out for now, 1.3/1.4): once
  there's real swipe history to learn from, rank incoming search results
  by predicted interest rather than pure relevance/recency/citations.
  Even a simple TF-IDF or embedding-similarity model over
  previously-saved vs. skipped abstracts would be a meaningful v2 step
  before reaching for anything heavier — kept deliberately out of v1 so
  the core loop stays simple, transparent, and trustworthy first (1.3).
- **Cross-session Saved List persistence** (3.5/3.6): letting saved
  papers accumulate across multiple searches instead of resetting per
  search session — straightforward once there's a reason users are
  hitting the current per-session limit in practice.
- **Search history**: browsing/re-running past queries, beyond v1's
  single sticky "last settings" pre-fill (3.5/3.6).

### 14.2 Audio system

- **Self-hosted open-source neural TTS** (Piper, with Kokoro-TTS and
  Coqui as evaluated alternatives — 6.7): the planned v2 engine
  migration, motivated by voice consistency, pronunciation control, and
  real word-level timestamps for tighter highlight sync.
- **Fixes the background/lock-screen audio gap** (13.2) as a side effect
  of the same migration — pre-rendered audio files can play through a
  real `<audio>` element + Media Session API, which v1's live
  `speechSynthesis` calls cannot do reliably.
- **Curated biomedical pronunciation dictionary** (6.3): gene/protein/
  species names were explicitly left as a known v1 quality gap; a
  dictionary built from real listening-session pain points is a natural
  post-v1 investment, and pairs naturally with the self-hosted engine
  migration (which allows lexicon/phoneme-level overrides that the Web
  Speech API doesn't expose at all).
- **Podcast-style narration format** (1.4, 5.2): an alternative to the
  audiobook/TTS default, already reserved a (disabled) slot in the
  Search & Settings wireframe.

### 14.3 Zotero

- **Group library support** (8.9): pushing into shared/lab Zotero group
  libraries, not just the personal library — deferred for added
  complexity (which group, group-specific permissions) with no validated
  demand yet.

### 14.4 Platform & scale

- **Multi-tab/multi-device session sync** (13.5): currently an explicit
  non-goal; would need the real-time layer (WebSocket/SSE) that 10.6
  deliberately avoided for v1, so this is coupled to a bigger
  architectural decision, not a small add-on.
- **Observability/error tracking** (e.g. Sentry, 12.6): justified once
  there's real usage worth instrumenting.
- **Staging environment / deploy approval gate** (12.4): reasonable once
  more than one person is shipping changes.
- **Public/third-party API** (10.8): the backend currently exists only to
  serve LitList's own frontend; opening it up is a distinct product
  decision with its own auth/rate-limit implications, not an incremental
  step.
- **Affiliation-derived metadata (e.g. "country")** (7.4): dropped from
  v1 for lack of a reliable data source; worth revisiting if a better
  structured-affiliation data source is ever identified, rather than
  shipping a low-accuracy guess now.

### 14.5 What would make something graduate off this list

None of the above should move into a version's scope just because it's
on this list — the pattern established throughout this document is that
each v1 boundary was drawn for a stated reason (missing data source, no
validated demand, added complexity without a concrete need, or a
deliberate simplicity trade-off). The right trigger for picking something
up here is evidence: real usage surfacing a specific pain point, not the
roadmap item's mere existence.

---

## 15. Test Plans

Every tool recommended below is free and open-source (pytest, Vitest,
React Testing Library, Playwright, MSW, Lighthouse CI), consistent with
the stack priority set at the start of this document — nothing here
requires a paid testing SaaS. This section maps each test category to the
specific behaviors elsewhere in the spec that motivated it, rather than
listing generic "write tests" advice.

### 15.1 Backend unit tests

**Tooling:** `pytest` + `pytest-asyncio` (FastAPI's async routes need
async test functions) + `respx` (mocks `httpx` calls so tests never hit
real PubMed/iCite/Zotero endpoints).

Priority coverage, each tied to a specific correctness or security
requirement established earlier:

- `session_id` generation is CSPRNG-sourced and rotates on privilege
  escalation (9.1) — not just "a cookie gets set."
- Fernet encryption/decryption round-trip for `ZoteroConnection` tokens,
  and confirmation that `TOKEN_ENCRYPTION_KEY` and the database
  credentials are independent secrets (9.6).
- Sentence tokenizer is abbreviation-aware (6.4) — a dedicated test
  corpus of real abstract sentences containing "Fig. 2", "vs.", "e.g.",
  "et al.", and species abbreviations, asserting these do NOT get split
  mid-sentence.
- Two-tier pause-duration logic (structural vs. sentence-to-sentence, 6.4)
  produces the correct pause class for a given text-segment boundary.
- CSV/formula-injection sanitization on export (8.8) — inputs starting
  with `=`, `+`, `-`, `@` are neutralized in generated CSV cells.
- Outbound PubMed rate-limiter and inbound per-session/per-IP rate
  limiter (7.7, 10.5) are tested as two distinct code paths — see 15.8.

### 15.2 Frontend unit tests

**Tooling:** Vitest (pairs natively with the existing Vite build, 11.1) +
React Testing Library.

- Zustand store transitions: mute toggle, speed setting, decision state
  — pure state-logic tests, no DOM needed.
- The single decision function (11.4) that swipe, tap, and keyboard input
  all route through (5.3) — tested once, independent of *how* a decision
  was triggered, so gesture bugs and decision-logic bugs stay separable
  (see 15.10).
- Safe-array text rendering for untrusted PubMed title/abstract text
  (6.5/11.3) — assert rendered output never interprets HTML/script
  content from API responses; this is the regression test for the XSS
  fix made during the security pass.
- TanStack Query cache behavior for paper/search data (11.2).

### 15.3 Integration tests

- **Backend:** `httpx.AsyncClient` driving the full FastAPI route tree
  against a real (test-only) SQLite database — not mocks — to verify
  request/response contracts match Section 10 exactly, including the
  no-stack-trace-leakage error shape (10.3) and CORS headers (10.7).
- **Frontend:** Playwright tests against the built app with the backend
  replaced by **MSW (Mock Service Worker)**, exercising full user
  journeys from Section 4 (search → play → swipe → export) without
  depending on real PubMed/Zotero availability or rate limits.

### 15.4 Cross-browser & device compatibility

**Automated backbone:** Playwright, run across its three bundled engines
— Chromium (covers Chrome, Edge, Brave), Firefox, and WebKit. This is the
free/open-source way to get most of the desktop matrix named in Section 6
without paid device-cloud services.

**Explicit limitation:** Playwright's WebKit is a reasonable proxy for
Safari but is *not* identical to real iOS Safari — it misses iOS-specific
quirks in PWA install behavior, viewport handling, and (critically) the
`speechSynthesis` voice list, which is the exact area Section 6/13
already flags as fragile. Automated WebKit passing is necessary but not
sufficient.

**Manual release-candidate pass**, required before each release, on real
devices (or a free-tier-eligible open-source project account on a device
cloud such as BrowserStack, which several offer at no cost to open-source
projects):

- **15.4.1 Mobile Safari (iOS):** `SpeechSynthesis` voice availability and
  quality (known to differ from desktop Safari); the background/
  lock-screen audio limitation (13.2) — confirm current behavior hasn't
  silently changed; "Add to Home Screen" PWA install flow end-to-end.
- **15.4.2 Android Chrome:** `SpeechSynthesis` voice list; the native
  install-banner prompt timing/behavior; Wake Lock API support (13.x)
  actually keeping the screen on during playback.

### 15.5 PWA install

**Tooling:** Lighthouse CI (free, open-source, Google), run in the PR
pipeline (12.4) to automatically assert the installability criteria —
valid manifest, registered service worker, correctly sized icons.
Lighthouse checks the *criteria* for installability, not the actual OS
install prompt/UX, so this is supplemented by the manual install pass in
15.4 on real iOS/Android/desktop before each release.

### 15.6 Offline mode

Using Playwright's network-offline emulation (no real airplane-mode
device needed for the automated pass):

- App shell (cached via the service worker, 11.5) still loads with no
  network.
- A swipe session already in progress doesn't crash when connectivity
  drops mid-session (edge case in 4.4) — degrades to the user-facing
  offline messaging specified there, rather than throwing an
  unhandled error.
- Reconnect behavior: any decision made while offline is not silently
  dropped once the network returns.

### 15.7 OAuth flow (Zotero)

The full flow (8.2, with the 9.6/10.2 security additions) is hard to
exercise end-to-end against real Zotero in CI, so it splits into two
tiers:

- **Automated:** unit/integration tests against a mocked OAuth 1.0a
  provider (`respx` stubbing `/oauth/request`, `/oauth/authorize`,
  `/oauth/access`), specifically covering the security-pass fixes —
  request-token-to-session binding is enforced (10.2 addendum), a
  mismatched or expired request token is rejected, and the callback
  redirect target is the fixed allow-listed URL rather than
  attacker-controlled (8.2's open-redirect fix).
- **Manual smoke test**, before each release, against a real Zotero
  sandbox/test account — Zotero's actual API behavior is an external
  dependency outside this project's control, so an automated mock alone
  can silently drift from reality.

### 15.8 PubMed rate limiting

Two genuinely separate mechanisms, tested separately so they can't be
conflated (a mistake the security pass explicitly called out, 10.5):

- **Outbound pacing** (7.7 — 10 req/s with `NCBI_API_KEY`, 3 req/s
  without): unit-tested against a fake/injectable clock, never real
  `sleep()` calls, so the suite stays fast; a mocked E-utilities endpoint
  returning `429`/`Retry-After` confirms the backoff logic actually
  backs off.
- **Inbound per-session/per-IP limiter** (10.5, the abuse-prevention
  gap found during the security pass): integration-tested by issuing
  requests past the threshold from a single test session/IP and asserting
  the correct `429` response — independent of the outbound-pacing tests
  above.

### 15.9 TTS synchronization

Web Speech API's `boundary` events are not perfectly reliable across
browsers, which is exactly why Section 6 specified a timer-based
fallback. Tests here exist to catch regressions in that specific design:

- The timer-fallback path is deliberately exercised (simulate a browser
  that never fires `boundary` events) so it can't silently rot into dead,
  untested code.
- Sentence-tokenizer output is checked as a golden-file/snapshot test
  against a fixed corpus of real abstracts with known-tricky abbreviations
  — regression coverage for the fix in 15.1, now from the
  synchronization-timing side.
- Mute (`utterance.volume = 0`, per the mute-button redesign in Section
  6) still advances highlighting on the *same* clock as unmuted
  playback — this is the regression test for that specific
  architectural simplification.
- The speed setting scales both audio playback rate and highlight-advance
  timing together, never independently — regression coverage for the
  consolidation decision made in Section 6.

### 15.10 Gesture testing

Framer Motion drag gestures don't have a real pointer/gesture engine in
jsdom, so this splits by what's actually being tested:

- **Playwright** (real mouse/touch event emulation) covers the physical
  drag interaction itself: swipe-left/right distance thresholds,
  cancel-mid-drag snap-back animation, and that tap/click and keyboard
  input (5.3) all visibly trigger the same result as a completed swipe.
- **Unit tests** cover the pure decision function (11.4) that all three
  input methods route through, in isolation from any gesture engine —
  so a bug in swipe-threshold math and a bug in decision-routing logic
  fail in two different, clearly-named tests rather than one entangled
  end-to-end test.

### 15.11 CI integration

All of the above except the manual release-candidate passes (15.4.1,
15.4.2, 15.5's OS-level check, 15.7's real-Zotero smoke test) run in the
existing PR pipeline (12.4), blocking merge on failure — no new pipeline
is introduced, this section fills in what "test suite for both" in 12.4
actually consists of. The manual passes are a release-checklist item, not
a per-PR gate, since they need real devices/accounts and would otherwise
make every PR wait on hardware availability.

---

*This is the final section. The specification is complete end-to-end —
Vision through Test Plans — and ready to hand to an implementation agent,
with the understanding that anything marked as a deferred/future item
anywhere in this document is intentionally excluded from a v1 build.*
