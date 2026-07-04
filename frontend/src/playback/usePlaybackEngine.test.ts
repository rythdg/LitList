import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { UNSUPPORTED_NOTICE, usePlaybackEngine } from "./usePlaybackEngine";
import type { PlaybackEngineEnv, PlaybackItem, UtteranceLike, WakeLockSentinelLike } from "./types";

/**
 * SPEC.md §15.9 (TTS synchronization) test coverage for BuildPlan Task
 * 2D's `usePlaybackEngine`. Every test drives the hook through a fully
 * injectable `PlaybackEngineEnv` (manual timer queue, fake/absent synth,
 * mocked wake lock) rather than real browser timers/speech synthesis —
 * this is what makes the timer-fallback path *actually* exercised
 * (fired and asserted on), not just present in code.
 */

interface ScheduledTimer {
  id: number;
  ms: number;
  cb: () => void;
  cancelled: boolean;
  fired: boolean;
}

function createManualClock() {
  let nextId = 1;
  const scheduled: ScheduledTimer[] = [];

  const setTimeoutFn = (cb: () => void, ms: number): number => {
    const id = nextId++;
    scheduled.push({ id, ms, cb, cancelled: false, fired: false });
    return id;
  };
  const clearTimeoutFn = (id: number) => {
    const entry = scheduled.find((s) => s.id === id);
    if (entry) entry.cancelled = true;
  };

  /** Fires the oldest still-pending timer (FIFO), returning its recorded
   *  delay in ms so tests can assert on speed-scaling without needing
   *  real elapsed time. */
  function fireNext(): number {
    const entry = scheduled.find((s) => !s.cancelled && !s.fired);
    if (!entry) throw new Error("No pending timer to fire");
    entry.fired = true;
    entry.cb();
    return entry.ms;
  }

  return { setTimeoutFn, clearTimeoutFn, fireNext };
}

function createFakeUtterance(text: string): UtteranceLike {
  return { text, rate: 1, volume: 1, onend: null, onerror: null, onboundary: null };
}

function makeEnv(opts: {
  withSynth: boolean;
  clock: ReturnType<typeof createManualClock>;
  wakeLock?: WakeLockSentinelLike | null;
}): { env: PlaybackEngineEnv; speak: ReturnType<typeof vi.fn>; cancel: ReturnType<typeof vi.fn> } {
  const speak = vi.fn();
  const cancel = vi.fn();
  const requestWakeLock = vi.fn().mockResolvedValue(opts.wakeLock ?? null);

  const env: PlaybackEngineEnv = {
    synth: opts.withSynth ? { speak, cancel } : undefined,
    createUtterance: opts.withSynth ? createFakeUtterance : undefined,
    setTimeoutFn: opts.clock.setTimeoutFn,
    clearTimeoutFn: opts.clock.clearTimeoutFn,
    requestWakeLock,
  };
  return { env, speak, cancel };
}

const items: PlaybackItem[] = [
  { key: "title", spokenText: "A short paper title", pauseClass: "structural" },
  { key: "seg-0", spokenText: "Prior work has shown mixed results across several independent studies", pauseClass: "sentence" },
  { key: "seg-1", spokenText: "We enrolled forty participants across two sites", pauseClass: "sentence" },
];

describe("usePlaybackEngine — timer-based fallback (§6.5/§13.7, §15.9)", () => {
  it("actually advances through items via the fallback timer when speech synthesis is unavailable", async () => {
    const clock = createManualClock();
    const { env } = makeEnv({ withSynth: false, clock });
    const onItemChange = vi.fn();
    const onFinished = vi.fn();

    const { result } = renderHook(() =>
      usePlaybackEngine({ items, speed: 1, muted: false, onItemChange, onFinished, env }),
    );

    expect(result.current.speechSupported).toBe(false);

    act(() => result.current.play());
    expect(result.current.usingFallbackTimer).toBe(true);
    expect(result.current.currentKey).toBe("title");

    // duration timer for "title" fires -> schedules the sentence gap
    act(() => {
      clock.fireNext();
    });
    // gap timer fires -> advances to the next item
    act(() => {
      clock.fireNext();
    });
    expect(result.current.currentKey).toBe("seg-0");

    // duration timer for seg-0, then gap into seg-1
    act(() => clock.fireNext());
    act(() => clock.fireNext());
    expect(result.current.currentKey).toBe("seg-1");

    // duration timer for seg-1 fires -> scheduleGap sees index 3 is past the
    // end of `items` and finishes immediately (no further timer scheduled).
    act(() => clock.fireNext());

    expect(result.current.status).toBe("finished");
    expect(result.current.currentKey).toBeNull();
    expect(onFinished).toHaveBeenCalledTimes(1);
    expect(onItemChange).toHaveBeenCalledWith("title");
    expect(onItemChange).toHaveBeenCalledWith("seg-0");
    expect(onItemChange).toHaveBeenCalledWith("seg-1");
    expect(onItemChange).toHaveBeenLastCalledWith(null);
  });
});

describe("usePlaybackEngine — mute (§6.5, §15.9)", () => {
  it("advances the highlight on the exact same clock whether muted or not", () => {
    const clockUnmuted = createManualClock();
    const unmutedEnv = makeEnv({ withSynth: true, clock: clockUnmuted });
    const unmuted = renderHook(() =>
      usePlaybackEngine({ items, speed: 1, muted: false, env: unmutedEnv.env }),
    );
    act(() => unmuted.result.current.play());
    const unmutedUtterance1 = unmutedEnv.speak.mock.calls[0][0] as UtteranceLike;
    expect(unmutedUtterance1.volume).toBe(1);
    act(() => unmutedUtterance1.onend?.());
    let unmutedGapMs = 0;
    act(() => {
      unmutedGapMs = clockUnmuted.fireNext();
    });
    expect(unmuted.result.current.currentKey).toBe("seg-0");

    const clockMuted = createManualClock();
    const mutedEnv = makeEnv({ withSynth: true, clock: clockMuted });
    const muted = renderHook(() =>
      usePlaybackEngine({ items, speed: 1, muted: true, env: mutedEnv.env }),
    );
    act(() => muted.result.current.play());
    const mutedUtterance1 = mutedEnv.speak.mock.calls[0][0] as UtteranceLike;
    expect(mutedUtterance1.volume).toBe(0);
    act(() => mutedUtterance1.onend?.());
    let mutedGapMs = 0;
    act(() => {
      mutedGapMs = clockMuted.fireNext();
    });
    expect(muted.result.current.currentKey).toBe("seg-0");

    // Same schedule either way — only volume differs.
    expect(mutedGapMs).toBe(unmutedGapMs);
  });

  it("live-applies a mute toggle to the in-flight utterance without touching the clock", () => {
    const clock = createManualClock();
    const { env, speak } = makeEnv({ withSynth: true, clock });
    const { result, rerender } = renderHook(
      ({ muted }: { muted: boolean }) => usePlaybackEngine({ items, speed: 1, muted, env }),
      { initialProps: { muted: false } },
    );

    act(() => result.current.play());
    const utterance = speak.mock.calls[0][0] as UtteranceLike;
    expect(utterance.volume).toBe(1);

    rerender({ muted: true });
    expect(utterance.volume).toBe(0);

    rerender({ muted: false });
    expect(utterance.volume).toBe(1);
  });
});

describe("usePlaybackEngine — speed scaling (§6.4, §15.9)", () => {
  it("scales both the utterance rate and the timer-driven gaps/durations together", () => {
    // Fallback-timer path: durations/gaps are computed entirely from speed.
    const clockSlow = createManualClock();
    const slowEnv = makeEnv({ withSynth: false, clock: clockSlow });
    const slow = renderHook(() => usePlaybackEngine({ items, speed: 1, muted: false, env: slowEnv.env }));
    act(() => slow.result.current.play());
    const slowDuration = clockSlow.fireNext(); // "title" duration timer

    const clockFast = createManualClock();
    const fastEnv = makeEnv({ withSynth: false, clock: clockFast });
    const fast = renderHook(() => usePlaybackEngine({ items, speed: 2, muted: false, env: fastEnv.env }));
    act(() => fast.result.current.play());
    const fastDuration = clockFast.fireNext();

    expect(fastDuration).toBeCloseTo(slowDuration / 2, 5);

    // Real-synth path: utterance.rate mirrors speed directly.
    const clockRate = createManualClock();
    const { env, speak } = makeEnv({ withSynth: true, clock: clockRate });
    const { result } = renderHook(() => usePlaybackEngine({ items, speed: 1.5, muted: false, env }));
    act(() => result.current.play());
    const utterance = speak.mock.calls[0][0] as UtteranceLike;
    expect(utterance.rate).toBe(1.5);
  });
});

describe("usePlaybackEngine — mid-narration cancellation (§6.6, §15.9)", () => {
  it("leaves no overlapping/orphaned utterances after cancel()", () => {
    const clock = createManualClock();
    const { env, speak, cancel } = makeEnv({ withSynth: true, clock });
    const onItemChange = vi.fn();

    const { result } = renderHook(() => usePlaybackEngine({ items, speed: 1, muted: false, onItemChange, env }));

    act(() => result.current.play());
    const utterance1 = speak.mock.calls[0][0] as UtteranceLike;
    expect(result.current.currentKey).toBe("title");

    act(() => result.current.cancel());
    expect(cancel).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe("idle");
    expect(result.current.currentKey).toBeNull();

    onItemChange.mockClear();

    // A late/stale onend firing after cancel() must be a no-op: no second
    // item change, no second speak() call, no crash.
    act(() => utterance1.onend?.());
    expect(onItemChange).not.toHaveBeenCalled();
    expect(speak).toHaveBeenCalledTimes(1);
    expect(result.current.currentKey).toBeNull();
    expect(result.current.status).toBe("idle");
  });
});

describe("usePlaybackEngine — play() re-entrancy (§11.3, §15.9)", () => {
  // Regression test for TASK 2D REVIEW's finding: React state updates
  // (`status`) don't commit synchronously within the same tick, so
  // guarding play()'s re-entrancy check on the `status` *state* value
  // let two synchronous play() calls (e.g. a double-tap, or two fast
  // Space keypresses handled in the same tick) both read the same
  // not-yet-committed "idle"/"paused" status and both fall through to
  // `env.synth.speak()` for the same item — audible duplicated
  // narration. The generation-counter ref stops a *stale* utterance's
  // onend/onerror from corrupting state, but does nothing to stop a
  // second *real* speak() call, since both calls capture the same
  // pre-bump generation before either commits. The fix guards on a
  // synchronous `statusRef` instead.
  it("calls speak() exactly once when play() is invoked twice synchronously in the same tick", () => {
    const clock = createManualClock();
    const { env, speak } = makeEnv({ withSynth: true, clock });

    const { result } = renderHook(() => usePlaybackEngine({ items, speed: 1, muted: false, env }));

    act(() => {
      result.current.play();
      result.current.play();
    });

    expect(speak).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe("playing");
    expect(result.current.currentKey).toBe("title");
  });

  it("calls speak() exactly once for three synchronous play() calls in the same tick", () => {
    const clock = createManualClock();
    const { env, speak } = makeEnv({ withSynth: true, clock });

    const { result } = renderHook(() => usePlaybackEngine({ items, speed: 1, muted: false, env }));

    act(() => {
      result.current.play();
      result.current.play();
      result.current.play();
    });

    expect(speak).toHaveBeenCalledTimes(1);
  });
});

describe("usePlaybackEngine — Screen Wake Lock (§13.2, §15.9)", () => {
  it("requests a wake lock when play() starts and releases it on cancel()", async () => {
    const clock = createManualClock();
    const release = vi.fn().mockResolvedValue(undefined);
    const wakeLock: WakeLockSentinelLike = { release };
    const requestWakeLock = vi.fn().mockResolvedValue(wakeLock);
    const env: PlaybackEngineEnv = {
      synth: undefined,
      createUtterance: undefined,
      setTimeoutFn: clock.setTimeoutFn,
      clearTimeoutFn: clock.clearTimeoutFn,
      requestWakeLock,
    };

    const { result } = renderHook(() => usePlaybackEngine({ items, speed: 1, muted: false, env }));

    await act(async () => {
      result.current.play();
      await Promise.resolve();
    });

    expect(requestWakeLock).toHaveBeenCalledTimes(1);

    await act(async () => {
      result.current.cancel();
      await Promise.resolve();
    });
    expect(release).toHaveBeenCalledTimes(1);
  });
});

describe("usePlaybackEngine — no Web Speech API support (§13.7)", () => {
  it("surfaces a one-time notice, dismissible, when speechSynthesis is entirely absent", () => {
    const clock = createManualClock();
    const { env } = makeEnv({ withSynth: false, clock });

    const { result } = renderHook(() => usePlaybackEngine({ items, speed: 1, muted: false, env }));

    expect(result.current.speechSupported).toBe(false);
    expect(result.current.unsupportedNotice).toBe(UNSUPPORTED_NOTICE);

    act(() => result.current.dismissUnsupportedNotice());
    expect(result.current.unsupportedNotice).toBeNull();
  });

  it("does not surface the notice when speech synthesis is supported", () => {
    const clock = createManualClock();
    const { env } = makeEnv({ withSynth: true, clock });

    const { result } = renderHook(() => usePlaybackEngine({ items, speed: 1, muted: false, env }));

    expect(result.current.speechSupported).toBe(true);
    expect(result.current.unsupportedNotice).toBeNull();
  });
});
