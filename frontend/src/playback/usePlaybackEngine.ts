import { useCallback, useEffect, useRef, useState } from "react";
import type {
  PauseClass,
  PlaybackEngineEnv,
  PlaybackItem,
  PlaybackStatus,
  SpeechSynthesisLike,
  UtteranceLike,
  WakeLockSentinelLike,
} from "./types";

/**
 * `usePlaybackEngine` — the single isolated playback module (SPEC.md
 * §11.3): per-sentence `SpeechSynthesisUtterance` queuing, the two
 * pause-class gaps (§6.4), mute-via-`volume` (§6.5), the timer-based
 * fallback (§6.5/§13.7), `onboundary` as bonus-only precision (never
 * implemented here as a dependency — see note below), Screen Wake Lock
 * while playing (§13.2), and `speechSynthesis.cancel()` as the one place
 * mid-narration cancellation happens (§6.6).
 *
 * Consumes, never computes, segmentation/pause-class decisions — callers
 * hand this hook an ordered `items: PlaybackItem[]` (title, metadata,
 * abstract segments in play order) built from CONTRACTS.md's pinned
 * `AbstractSegment` shape (plus whatever not-yet-pinned title/metadata
 * shape a later task supplies); this module only ever reads
 * `item.pauseClass`, never re-derives it.
 *
 * State ownership note (§11.2 vs §11.3): whether narration is "playing"
 * and whether it's "muted" are Zustand-owned facts, not this hook's own
 * state — so `muted`/`speed` are accepted here as *reactive inputs*
 * (props), not re-declared as internal state, to avoid the same fact
 * living in two places. This hook owns only the mechanics (utterance
 * queue, timers, wake lock) needed to make those external facts actually
 * happen.
 */

const STRUCTURAL_PAUSE_MS = 900; // §6.4: "~800ms-1s" section-break gap
const SENTENCE_PAUSE_MS = 250; // §6.4: "~150-350ms" within-abstract gap
const WORDS_PER_MINUTE_AT_1X = 165; // natural reading-pace baseline for the timer fallback
const MIN_FALLBACK_DURATION_MS = 150;

export const UNSUPPORTED_NOTICE =
  "Audio narration isn't available in this browser — you can still read along.";

function pauseDurationMs(pauseClass: PauseClass, speed: number): number {
  const base = pauseClass === "structural" ? STRUCTURAL_PAUSE_MS : SENTENCE_PAUSE_MS;
  return base / speed;
}

function estimateSpeechDurationMs(text: string, speed: number): number {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  const ms = (words / WORDS_PER_MINUTE_AT_1X) * 60_000;
  return Math.max(ms, MIN_FALLBACK_DURATION_MS) / speed;
}

function defaultEnv(): PlaybackEngineEnv {
  const hasWindow = typeof window !== "undefined";
  const hasSpeech =
    hasWindow && "speechSynthesis" in window && typeof window.SpeechSynthesisUtterance === "function";

  return {
    synth: hasSpeech ? (window.speechSynthesis as unknown as SpeechSynthesisLike) : undefined,
    createUtterance: hasSpeech
      ? (text: string) => new window.SpeechSynthesisUtterance(text) as unknown as UtteranceLike
      : undefined,
    setTimeoutFn: (cb, ms) => window.setTimeout(cb, ms) as unknown as number,
    clearTimeoutFn: (id) => window.clearTimeout(id),
    requestWakeLock: async () => {
      if (typeof navigator === "undefined" || !("wakeLock" in navigator)) return null;
      try {
        const wakeLock = (
          navigator as Navigator & {
            wakeLock: { request(type: "screen"): Promise<WakeLockSentinelLike> };
          }
        ).wakeLock;
        return await wakeLock.request("screen");
      } catch {
        return null;
      }
    },
  };
}

export interface UsePlaybackEngineOptions {
  /** Ordered narration queue for the current paper. */
  items: PlaybackItem[];
  /** Speed multiplier (1 = normal). Scales both `utterance.rate` and every
   *  timer-driven duration/gap together — §15.9's "never independently"
   *  regression requirement. */
  speed: number;
  /** Owned externally (Zustand, §11.2) — this hook only applies it. */
  muted: boolean;
  /** Fired whenever the highlighted item changes; `null` when nothing is
   *  current (idle/cancelled/finished). */
  onItemChange?: (key: string | null) => void;
  /** Fired once the last item's gap+utterance has completed. */
  onFinished?: () => void;
  /** Injection seam for tests; omit to use real browser APIs. */
  env?: PlaybackEngineEnv;
}

export interface UsePlaybackEngineResult {
  status: PlaybackStatus;
  currentKey: string | null;
  /** Whether this environment has usable Web Speech API support at all. */
  speechSupported: boolean;
  /** True while the current item is being advanced by the timer fallback
   *  rather than a real utterance — exposed mainly for tests/telemetry. */
  usingFallbackTimer: boolean;
  /** Non-null exactly once (until dismissed) when `speechSupported` is
   *  false — §13.7's one-time notice. */
  unsupportedNotice: string | null;
  dismissUnsupportedNotice: () => void;
  play: () => void;
  pause: () => void;
  /** Full stop + reset to idle — the mid-narration swipe cancellation
   *  path (§6.6): calls `speechSynthesis.cancel()` synchronously and
   *  invalidates any in-flight timers so nothing can advance state after
   *  this returns. */
  cancel: () => void;
}

export function usePlaybackEngine(options: UsePlaybackEngineOptions): UsePlaybackEngineResult {
  const { items, speed, muted, onItemChange, onFinished } = options;

  // Resolved fresh each render from props (never from a ref) so it's safe
  // to read synchronously during render; the ref below is only ever
  // written inside an effect, never in the render body itself (React's
  // "no ref access during render" rule).
  const resolvedEnv = options.env ?? defaultEnv();
  const envRef = useRef<PlaybackEngineEnv>(resolvedEnv);
  useEffect(() => {
    envRef.current = resolvedEnv;
  }, [resolvedEnv]);

  const speechSupported = Boolean(resolvedEnv.synth && resolvedEnv.createUtterance);

  const [status, setStatus] = useState<PlaybackStatus>("idle");
  const [currentKey, setCurrentKey] = useState<string | null>(null);
  const [usingFallbackTimer, setUsingFallbackTimer] = useState(false);
  const [noticeDismissed, setNoticeDismissed] = useState(false);

  // React state updates don't commit synchronously within the same tick,
  // so two synchronous calls to play() (e.g. a double-tap or two fast
  // Space keypresses) would both see the *same* stale `status` value and
  // both pass a `status === "playing"` guard, each calling
  // `env.synth.speak()` for the same item — audibly duplicated narration.
  // The generation-counter ref already stops a *stale* utterance's
  // onend/onerror from corrupting state, but it does nothing to stop a
  // second *real* speak() call from happening in the first place, since
  // both calls capture the same pre-bump generation. `statusRef` is the
  // synchronous source of truth the re-entrancy guards below actually
  // check; `status` (state) remains only for driving UI re-renders.
  const statusRef = useRef<PlaybackStatus>("idle");
  const setStatusBoth = useCallback((next: PlaybackStatus) => {
    statusRef.current = next;
    setStatus(next);
  }, []);

  const itemsRef = useRef(items);
  useEffect(() => {
    itemsRef.current = items;
  }, [items]);
  const speedRef = useRef(speed);
  useEffect(() => {
    speedRef.current = speed;
  }, [speed]);
  const mutedRef = useRef(muted);
  useEffect(() => {
    mutedRef.current = muted;
  }, [muted]);

  const onItemChangeRef = useRef(onItemChange);
  useEffect(() => {
    onItemChangeRef.current = onItemChange;
  }, [onItemChange]);
  const onFinishedRef = useRef(onFinished);
  useEffect(() => {
    onFinishedRef.current = onFinished;
  }, [onFinished]);

  /** Index of the item currently playing (or about to resume from). */
  const indexRef = useRef(0);
  /** Bumped on every play()/pause()/cancel() so stale timer/utterance
   *  callbacks scheduled before the bump can recognize they're orphaned
   *  and no-op instead of advancing state — this is what guarantees "no
   *  overlapping/orphaned utterances" across a mid-narration cancel. */
  const generationRef = useRef(0);
  const pendingTimerRef = useRef<number | null>(null);
  const currentUtteranceRef = useRef<UtteranceLike | null>(null);
  const wakeLockRef = useRef<WakeLockSentinelLike | null>(null);

  const clearPendingTimer = useCallback(() => {
    if (pendingTimerRef.current !== null) {
      envRef.current.clearTimeoutFn(pendingTimerRef.current);
      pendingTimerRef.current = null;
    }
  }, []);

  const releaseWakeLock = useCallback(() => {
    const lock = wakeLockRef.current;
    wakeLockRef.current = null;
    if (lock) void lock.release().catch(() => {});
  }, []);

  const setCurrentItem = useCallback((key: string | null) => {
    setCurrentKey(key);
    onItemChangeRef.current?.(key);
  }, []);

  const finish = useCallback(() => {
    releaseWakeLock();
    setStatusBoth("finished");
    setCurrentItem(null);
    onFinishedRef.current?.();
  }, [releaseWakeLock, setCurrentItem, setStatusBoth]);

  // playItem/scheduleGap call each other, so they're wired through refs to
  // dodge a useCallback circular-dependency without reaching for a class.
  const playItemImplRef = useRef<(index: number, generation: number) => void>(() => {});

  const scheduleGap = useCallback(
    (nextIndex: number, generation: number) => {
      if (generation !== generationRef.current) return;
      const currentItems = itemsRef.current;
      if (nextIndex >= currentItems.length) {
        finish();
        return;
      }
      const pauseMs = pauseDurationMs(currentItems[nextIndex].pauseClass, speedRef.current);
      pendingTimerRef.current = envRef.current.setTimeoutFn(() => {
        if (generation !== generationRef.current) return; // stale — cancelled/paused since
        playItemImplRef.current(nextIndex, generation);
      }, pauseMs);
    },
    [finish],
  );

  const playItem = useCallback(
    (index: number, generation: number) => {
      if (generation !== generationRef.current) return;
      const currentItems = itemsRef.current;
      if (index >= currentItems.length) {
        finish();
        return;
      }
      const item = currentItems[index];
      indexRef.current = index;
      setCurrentItem(item.key);

      const env = envRef.current;
      if (env.synth && env.createUtterance) {
        try {
          const utterance = env.createUtterance(item.spokenText);
          utterance.rate = speedRef.current;
          utterance.volume = mutedRef.current ? 0 : 1;
          utterance.onend = () => {
            if (generation !== generationRef.current) return;
            currentUtteranceRef.current = null;
            scheduleGap(index + 1, generation);
          };
          utterance.onerror = () => {
            if (generation !== generationRef.current) return;
            currentUtteranceRef.current = null;
            scheduleGap(index + 1, generation);
          };
          currentUtteranceRef.current = utterance;
          setUsingFallbackTimer(false);
          env.synth.speak(utterance);
          return;
        } catch {
          // Genuine engine failure (§6.5/§13.7) — fall through to the
          // timer-based fallback below rather than erroring out.
        }
      }

      // Timer-based fallback: no speech support, or speak()/createUtterance
      // threw. This is the "TTS isn't working" clock (§6.5), never used
      // just because the user muted — mute keeps using the real utterance
      // clock (see the volume effect below).
      setUsingFallbackTimer(true);
      const durationMs = estimateSpeechDurationMs(item.spokenText, speedRef.current);
      pendingTimerRef.current = env.setTimeoutFn(() => {
        if (generation !== generationRef.current) return;
        scheduleGap(index + 1, generation);
      }, durationMs);
    },
    [finish, scheduleGap, setCurrentItem],
  );

  useEffect(() => {
    playItemImplRef.current = playItem;
  }, [playItem]);

  // Live-apply mute to whatever utterance is currently speaking, without
  // touching the timing clock at all (§6.5/§15.9: mute must advance the
  // highlight on the exact same schedule as unmuted playback).
  useEffect(() => {
    if (currentUtteranceRef.current) {
      currentUtteranceRef.current.volume = muted ? 0 : 1;
    }
  }, [muted]);

  const play = useCallback(() => {
    // Guard on the synchronous ref, not the `status` state value: two
    // synchronous play() calls in the same tick (double-tap, two fast
    // Space keypresses) would otherwise both read the same
    // not-yet-committed `status` and both fall through to
    // `env.synth.speak()` — audibly duplicated narration, not just a
    // state-consistency issue.
    if (statusRef.current === "playing") return;
    const generation = (generationRef.current += 1);
    setStatusBoth("playing");
    // Fire-and-forget by design: the wake lock is a best-effort mitigation
    // (§13.2), never something narration should block on. Note for anyone
    // chasing the still-unexplained intermittent mute-test flake reported
    // in TASK 2B VERIFY: this callback only ever writes a plain ref
    // (`wakeLockRef.current`) or calls `lock?.release()` — it has no path
    // to React state (`currentKey`/`status`), so on inspection it cannot
    // be the direct cause of a `currentKey`-assertion flake. Adversarial
    // review (TASK 2D REVIEW) could not reproduce the flake either after
    // 200+256 iterations; it remains open/unexplained rather than closed.
    // If revisiting, the more useful lead is probably test-harness timing
    // (unawaited promise settling mid-test, tripping an act() warning)
    // rather than a state-correctness bug in this hook.
    void envRef.current.requestWakeLock().then((lock) => {
      if (generation !== generationRef.current) {
        void lock?.release().catch(() => {});
        return;
      }
      wakeLockRef.current = lock;
    });
    playItem(indexRef.current, generation);
  }, [playItem, setStatusBoth]);

  const pause = useCallback(() => {
    if (statusRef.current !== "playing") return;
    // §6.2: Web Speech pause/resume isn't reliable across browsers (the
    // same reason 6.5 chose mute-via-volume over engine pause). The pause
    // button applies that same conservative logic: stop everything and
    // resume() re-speaks the current item from its start rather than
    // trusting a native mid-utterance resume.
    generationRef.current += 1;
    clearPendingTimer();
    envRef.current.synth?.cancel();
    currentUtteranceRef.current = null;
    releaseWakeLock();
    setStatusBoth("paused");
  }, [clearPendingTimer, releaseWakeLock, setStatusBoth]);

  const cancel = useCallback(() => {
    generationRef.current += 1;
    clearPendingTimer();
    envRef.current.synth?.cancel();
    currentUtteranceRef.current = null;
    releaseWakeLock();
    indexRef.current = 0;
    setStatusBoth("idle");
    setCurrentItem(null);
  }, [clearPendingTimer, releaseWakeLock, setCurrentItem, setStatusBoth]);

  // Unmount safety net: make sure nothing keeps talking after the
  // component using this hook goes away.
  useEffect(() => {
    return () => {
      generationRef.current += 1;
      clearPendingTimer();
      envRef.current.synth?.cancel();
      releaseWakeLock();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const unsupportedNotice = !speechSupported && !noticeDismissed ? UNSUPPORTED_NOTICE : null;

  return {
    status,
    currentKey,
    speechSupported,
    usingFallbackTimer,
    unsupportedNotice,
    dismissUnsupportedNotice: () => setNoticeDismissed(true),
    play,
    pause,
    cancel,
  };
}
