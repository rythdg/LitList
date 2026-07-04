/**
 * Local types for the playback engine (Task 2D — SPEC.md §6, §11.3).
 *
 * `PauseClass` mirrors CONTRACTS.md §1's `AbstractSegment.pause_class` —
 * a *category* ("structural" | "sentence") decided once, by the backend
 * tokenizer (Task 1D). This module never re-derives that category or the
 * sentence split itself; it only maps the category to an actual
 * millisecond gap, scaled by the user's Speed setting. That mapping is
 * *not* something CONTRACTS.md pins a number for — SPEC.md §6.4 says the
 * exact value is "tuned per the active Speed setting... during
 * implementation/testing, not fixed at one number," and Speed is
 * local-only client state (§11.2) the backend never sees — so the
 * category -> ms -> speed-scaled-gap conversion necessarily lives here,
 * in the playback engine, not in the backend tokenizer. This is distinct
 * from (and does not re-implement) the backend's job of deciding *which*
 * category a given gap belongs to.
 */
export type PauseClass = "structural" | "sentence";

/**
 * One item in the narration queue: the paper's title, its metadata line,
 * a section-header label, or one abstract sentence — the engine has no
 * opinion on which. `key` is an opaque identifier the engine hands back
 * via `onItemChange` so the UI can key its highlight off it; for
 * abstract segments this should be the segment's own `index` from
 * CONTRACTS.md's `AbstractSegment`, so the highlighting component never
 * needs a second lookup table.
 *
 * NOTE (flagged, not silently decided): CONTRACTS.md §1 only pins the
 * *abstract* segment shape (`segments[]`) — title/metadata line text is
 * part of the not-yet-pinned queue/paper response (Tier 3's job, §10.4).
 * This type is intentionally generic (`key` + `spokenText` +
 * `pauseClass`) so the engine stays decoupled from that not-yet-decided
 * shape; whoever assembles the combined [title, metadata, ...abstract
 * segments] queue (a later integration task) maps the real contract
 * shapes onto this list.
 */
export interface PlaybackItem {
  key: string;
  spokenText: string;
  pauseClass: PauseClass;
}

export type PlaybackStatus = "idle" | "playing" | "paused" | "finished";

/**
 * Minimal shape of `SpeechSynthesisUtterance` this module actually uses.
 * Kept as an interface (rather than importing the DOM lib type directly
 * everywhere) so tests can supply a plain object double instead of a real
 * `SpeechSynthesisUtterance` (which jsdom doesn't implement).
 */
export interface UtteranceLike {
  text: string;
  rate: number;
  volume: number;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  onboundary: (() => void) | null;
}

/** Minimal shape of `window.speechSynthesis` this module actually uses. */
export interface SpeechSynthesisLike {
  speak(utterance: UtteranceLike): void;
  cancel(): void;
}

/** Minimal shape of a Screen Wake Lock sentinel (§13.2). */
export interface WakeLockSentinelLike {
  release(): Promise<void>;
}

/**
 * All of this module's I/O with the outside world (speech synthesis,
 * timers, wake lock), injectable for tests. `synth`/`createUtterance`
 * being `undefined` means "no Web Speech API support" and is exactly
 * what triggers §13.7's timer-fallback path + one-time notice.
 */
export interface PlaybackEngineEnv {
  synth?: SpeechSynthesisLike;
  createUtterance?: (text: string) => UtteranceLike;
  setTimeoutFn: (cb: () => void, ms: number) => number;
  clearTimeoutFn: (id: number) => void;
  requestWakeLock: () => Promise<WakeLockSentinelLike | null>;
}
