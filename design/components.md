# LitList — Component Library

A component kit + working prototype for **LitList**, the hands-free PubMed
triage PWA described in `uploads/SPEC.md`. Everything here is built to be
assembled by an agentic system into the real React + TypeScript PWA (the spec's
frontend stack in §11), so components map 1:1 onto the screens and controls in
the spec's §5 wireframes.

## How it's built

- **Format:** every component is a self-contained **Design Component**
  (`.dc.html`) — it opens directly in a browser and is imported by other DCs
  with `<dc-import name="…">`.
- **Location:** all components live in **`assets/`**. Because `<dc-import>`
  resolves siblings by basename, the prototype (`assets/LitList.dc.html`) sits in
  the same folder so it can compose them.
- **Naming:** every component is prefixed **`LL`** (LitList) and named for its
  role, e.g. `LLPaperCard`, `LLSearchSettingsPanel`.

## Design language

Grounded in the bound **MindLink design system** tokens (`_ds/…/colors_and_type.css`)
with LitList's own art direction applied:

- **Type:** `Tahoma, Verdana, Geneva, 'DejaVu Sans', sans-serif` — clean, fast,
  universally available, no webfont load.
- **Surfaces:** white / warm off-white; hairline borders (`#E7E7E4`/`#EDEDEA`);
  restrained radii (8–16px); low warm shadows.
- **Accent:** MindLink orange `#F05A22` (inherited parent-brand accent) for the
  primary CTA, play button, active states — used as seasoning, one accent per screen.
- **Decision colors:** Interested = olive green `#6E9A1F` + heart; Skip = neutral
  grey `#595959` + ✕ (the one color-coded action pair, per spec §5.6).
- **Loaders:** orbiting-dots / synapse motif (`LLSynapseLoader`) — a nod to the
  parent brand, single-color, no bounce.
- **Icons:** hand-drawn inline SVG, single-weight ~1.75–2px stroke (Lucide-spirit).

Props marked *tweakable* expose an editor in the host Tweaks panel; props marked
*callback/data* (`editor: null`) are wired by the consuming app.

---

## Primitives & controls

### `LLWordmark` — `assets/LLWordmark.dc.html`
The LitList wordmark: "**Lit**List" (bold + regular) with an optional stacked-cards
+ play glyph. Use in nav, idle screen, splash.
Props: `size` (px), `showGlyph`, `accentColor`, `inkColor`.

### `LLButton` — `assets/LLButton.dc.html`
Primary action button. Variants `primary | secondary | ghost | danger | success`,
sizes `sm | md | lg`, plus `fullWidth`, `disabled`, `loading` (inline spinner).
Props: `label`, `variant`, `size`, `fullWidth`, `disabled`, `loading`, `onClick`, `ariaLabel`.

### `LLSearchBar` — `assets/LLSearchBar.dc.html`
Free-text PubMed query input (spec §5.2) with search icon, clear button, and an
inline loading spinner (loading never blocks the field). Submits on Enter.
Props: `value`, `placeholder`, `loading`, `autofocus`, `onInput(value)`, `onSubmit(value)`.

### `LLRadioGroup` — `assets/LLRadioGroup.dc.html`
Single-select group used for **Sort by**, **If I don't swipe**, and **Narration
format** (supports per-option `disabled` + `hint` for the greyed "Podcast — coming
later"). Fully keyboard/label accessible.
Props: `legend`, `value`, `name`, `options: {value,label,hint?,disabled?}[]`, `onChange(value)`.

### `LLCheckboxField` — `assets/LLCheckboxField.dc.html`
One checkbox row for the **Read aloud** field toggles (last author, all authors,
journal, publication date). Compose several.
Props: `label`, `hint`, `checked`, `disabled`, `onChange(checked)`.

### `LLSpeedSlider` — `assets/LLSpeedSlider.dc.html`
The single **Speed** control (spec's one unified narration + highlight rate) with a
live numeric readout (e.g. `1.1×`) and orange fill track.
Props: `label`, `value`, `min`, `max`, `step`, `unit`, `onChange(value)`.

---

## Feedback & status

### `LLSynapseLoader` — `assets/LLSynapseLoader.dc.html`
The research-themed loader: orbiting synapse nodes around a pulsing core. Use for
PubMed fetches, Zotero saves, any wait. Optional label.
Props: `size` (px), `color`, `nodeCount`, `label`.

### `LLToast` — `assets/LLToast.dc.html`
Transient status message. Variants `info | success | error`, optional inline action
(e.g. "Nothing saved yet", "CSV downloaded", "Retry").
Props: `message`, `variant`, `actionLabel`, `onAction`.

### `LLEmptyState` — `assets/LLEmptyState.dc.html`
Full empty/idle states with a line illustration. Variants `no-results` (spec §5.3a),
`nothing-saved` (empty saved list), `offline` (spec §4.5). Optional action button.
Props: `variant`, `title`, `message`, `actionLabel`, `onAction`.

---

## Playback

### `LLPlayButton` — `assets/LLPlayButton.dc.html`
The large primary play/pause control (spec §5.3). Orange, brand-shadowed, with an
optional pulsing ring while playing and a disabled state (greyed, with a `shake`
affordance for the empty-results case).
Props: `playing`, `disabled`, `pulse`, `size` (px), `onClick`.

### `LLMuteButton` — `assets/LLMuteButton.dc.html`
Small mute toggle beside the play button (spec §5.3). Toggles **audio output only**
— per the spec it never pauses playback or the highlight.
Props: `muted`, `size` (px), `onClick`.

---

## Triage (the core loop)

### `LLAbstractReader` — `assets/LLAbstractReader.dc.html`
Karaoke-style abstract renderer. Takes a **pre-split array of sentences** and a
`currentIndex`; highlights the current sentence, dims upcoming ones, keeps read
ones neutral. Renders each sentence as a plain text `<span>` (no
`dangerouslySetInnerHTML`) — the XSS-safe pattern mandated by spec §6.5/§11.3 for
untrusted PubMed text. Shows an idle prompt until `active`.
Props: `sentences: string[]`, `currentIndex`, `active`, `idleText`, `maxHeight`.

### `LLPaperCard` — `assets/LLPaperCard.dc.html`
The current-paper card and the heart of the loop. Composes `LLAbstractReader`, shows
title + configurable metadata line, and is **drag-to-decide**: swipe right =
Interested (green check overlay), left = Skip (grey ✕ overlay), with the arc/tint
animation from spec §5.3b. Also accepts a `decideSignal` so button/keyboard/auto
decisions play the *same* exit animation (one decision path, spec §11.4).
Props: `title`, `metaLine`, `sentences`, `currentIndex`, `active`, `draggable`,
`idleText`, `onDecide(dir)`, `decideSignal:{dir,nonce}`.

### `LLNextUpPreview` — `assets/LLNextUpPreview.dc.html`
Title-only preview of the next paper (spec §5.3). Non-interactive; shows "End of
queue" when empty.
Props: `title`.

### `LLDecisionButtons` — `assets/LLDecisionButtons.dc.html`
Tap/click/keyboard-accessible Skip / Interested pair — the required non-swipe
equivalent (spec §13.1). Green heart + neutral ✕, matching the swipe overlays.
Props: `disabled`, `showLabels`, `size` (px), `onSkip`, `onInterested`.

### `LLSwipeAffordance` — `assets/LLSwipeAffordance.dc.html`
The subtle bobbing "swipe down to search" / "swipe up for saved list" hints. Also a
tappable button (discoverability) and supports a disabled state (empty saved list).
Props: `direction: 'up'|'down'`, `label`, `disabled`, `onClick`.

### `LLSavedPaperItem` — `assets/LLSavedPaperItem.dc.html`
One row in the saved list: title (2-line clamp) + metadata + a remove (✕) button
(remove-only, does not re-queue — spec §4.7).
Props: `title`, `meta`, `onRemove`.

---

## Panels (composed surfaces)

### `LLSearchSettingsPanel` — `assets/LLSearchSettingsPanel.dc.html`
Screen B (spec §5.2). Composes `LLSearchBar`, three `LLRadioGroup`s (sort / default
behavior / format), four `LLCheckboxField`s (read-aloud), `LLSpeedSlider`, and a
`LLButton` Start CTA. Controlled: reads a `settings` object, emits the merged object
via `onChange`. Start is disabled on a blank query.
Props: `query`, `settings`, `loading`, `resultCount`, `onChange(settings)`,
`onQueryChange(q)`, `onStart`, `onClose`.
`settings` shape: `{ sort, fields:{lastAuthor,allAuthors,journal,pubDate},
defaultBehavior, speed, format }`.

### `LLSavedListPanel` — `assets/LLSavedListPanel.dc.html`
Screen D (spec §5.4). A count header, a list of `LLSavedPaperItem`s (or an
`LLEmptyState`), and the two export actions (Push to Zotero / Download CSV) plus the
Zotero connection status + Disconnect (shown only when connected — spec §9.6).
Props: `papers:{id,title,meta}[]`, `connected`, `zoteroUser`, `onRemove(id)`,
`onPushZotero`, `onDownloadCsv`, `onDisconnect`, `onClose`.

### `LLZoteroPushDialog` — `assets/LLZoteroPushDialog.dc.html`
Screen D1 (spec §5.5). One modal with five steps via a `step` prop:
`connect → choose → saving → success → error`. Includes inline "+ New collection",
an offline "pending — will retry" variant, and an error state that distinguishes
auth vs push failure and always offers the CSV fallback (spec §4.4). Backdrop blur.
Props: `step`, `paperCount`, `collections:{id,name}[]`, `selectedId`, `targetName`,
`errorKind:'auth'|'push'`, `errorMessage`, `offline`, `onConnect`, `onSave(target)`,
`onCancel`, `onDone`, `onRetry`, `onDownloadCsv`.

---

## Prototype

### `LitList` — `assets/LitList.dc.html`
The full working PWA prototype, composing every component above into the
single-surface, gesture-driven IA (spec §3). It owns all orchestration state and a
**real Web Speech API playback engine**:

- **Navigation:** swipe down (or tap affordance / ↓) → Search & Settings; swipe up
  (or ↑) → Saved list; Escape / close buttons collapse. Panels slide over the Stack
  Screen from top and bottom.
- **Real TTS:** on Play, the browser's `speechSynthesis` narrates title → (pause) →
  metadata line → (pause) → abstract, one `SpeechSynthesisUtterance` per sentence;
  the current sentence index drives `LLAbstractReader`'s highlight (utterance-boundary
  clock, no `onboundary` dependency). Falls back to a word-count timer if TTS is
  unavailable (spec §6.5). Speed maps to `utterance.rate`.
- **Mute** silences output (`volume`) without stopping playback or the highlight.
- **Decisions:** swipe / Skip / Interested / ← → / auto-decide-at-end all funnel
  through one path; auto-decide obeys the "If I don't swipe" default and plays an
  end-of-paper chime (or a visual pulse when muted).
- **Flow:** search (with loading + empty-results states) → triage → saved list →
  Zotero push (connect → choose → save → success) or CSV download, with toasts.

Mock PubMed data (six neuroscience papers) stands in for the live API. Open this
file to use the app.

---

## Notes & assumptions

- **PubMed / Zotero are mocked** in the prototype (search latency, result counts,
  OAuth, collections, and the save round-trip are simulated). The components take
  plain data + callbacks, so wiring them to the real §7/§8/§10 endpoints is a
  drop-in for the build system.
- **Text normalization** (spec §6.3 — expanding `et al.`, units, Greek, stats) is
  represented lightly; abstracts are authored clean and pre-split into sentences.
  Production should run the full normalizer to produce the "spoken" vs "display"
  text pair and feed spoken text to `LLAbstractReader`/TTS.
- **Offline** (spec §4.5) has an `LLEmptyState variant="offline"` and an offline
  path in `LLZoteroPushDialog`, but the prototype does not simulate connectivity loss.
- All components are controlled/stateless where practical, so the build system holds
  server state in TanStack Query and local state in Zustand exactly as spec §11.2
  prescribes.
