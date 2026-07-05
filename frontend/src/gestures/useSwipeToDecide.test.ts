import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { COMMIT_THRESHOLD_PX, useSwipeToDecide } from "./useSwipeToDecide";
import type { PanInfo } from "framer-motion";

function panInfo(offsetX: number, offsetY = 0): PanInfo {
  return {
    offset: { x: offsetX, y: offsetY },
    point: { x: offsetX, y: offsetY },
    delta: { x: 0, y: 0 },
    velocity: { x: 0, y: 0 },
  };
}

/**
 * §11.4/§15.10 regression: swipe (a completed drag), tap, and keyboard
 * must all invoke the exact same decision function with the exact same
 * arguments for an equivalent decision — this is the specific
 * "swipe-threshold math bug and decision-routing bug fail in two
 * different, clearly-named tests" case SPEC.md §15.10 calls out, tested
 * here in isolation from any real gesture/pointer engine (jsdom has
 * none, per §15.10's own note).
 *
 * Each input method below gets its *own* `renderHook` instance — this
 * matches real usage (`App.tsx` mounts a fresh `StackScreen`, and
 * therefore a fresh `useSwipeToDecide`, per card via `key={pmid}`) and
 * is also what the re-entrancy guard below requires: once one instance
 * commits a decision, that same instance is guaranteed never to commit
 * a second one (see the dedicated "re-entrancy" describe block).
 */
describe("useSwipeToDecide (§11.4 single decision function, §15.10)", () => {
  it("a rightward drag past the commit threshold calls onDecide the same way a tap and a keyboard trigger do", () => {
    const onDecide = vi.fn();

    const swipe = renderHook(() => useSwipeToDecide({ onDecide }));
    act(() => {
      swipe.result.current.dragProps.onDragEnd(
        {} as unknown as PointerEvent,
        panInfo(COMMIT_THRESHOLD_PX + 5),
      );
    });
    expect(onDecide).toHaveBeenCalledTimes(1);
    expect(onDecide).toHaveBeenCalledWith("interested", "swipe");

    onDecide.mockClear();
    const tap = renderHook(() => useSwipeToDecide({ onDecide }));
    act(() => {
      tap.result.current.triggerDecision("interested", "tap");
    });
    expect(onDecide).toHaveBeenCalledTimes(1);
    expect(onDecide).toHaveBeenCalledWith("interested", "tap");

    onDecide.mockClear();
    const keyboard = renderHook(() => useSwipeToDecide({ onDecide }));
    act(() => {
      keyboard.result.current.triggerDecision("interested", "keyboard");
    });
    expect(onDecide).toHaveBeenCalledTimes(1);
    expect(onDecide).toHaveBeenCalledWith("interested", "keyboard");

    // Same decision value across all three input methods, only `source`
    // differs — proving they're one function with three entry points,
    // not three divergent implementations.
  });

  it("a leftward drag past the commit threshold produces the same call shape as tap/keyboard for not_interested", () => {
    const onDecide = vi.fn();

    const swipe = renderHook(() => useSwipeToDecide({ onDecide }));
    act(() => {
      swipe.result.current.dragProps.onDragEnd(
        {} as unknown as PointerEvent,
        panInfo(-(COMMIT_THRESHOLD_PX + 5)),
      );
    });
    expect(onDecide).toHaveBeenCalledWith("not_interested", "swipe");

    onDecide.mockClear();
    const tap = renderHook(() => useSwipeToDecide({ onDecide }));
    act(() => {
      tap.result.current.triggerDecision("not_interested", "tap");
    });
    expect(onDecide).toHaveBeenCalledWith("not_interested", "tap");

    onDecide.mockClear();
    const keyboard = renderHook(() => useSwipeToDecide({ onDecide }));
    act(() => {
      keyboard.result.current.triggerDecision("not_interested", "keyboard");
    });
    expect(onDecide).toHaveBeenCalledWith("not_interested", "keyboard");
  });

  it("does not call onDecide for a drag below the commit threshold", () => {
    const onDecide = vi.fn();
    const { result } = renderHook(() => useSwipeToDecide({ onDecide }));

    act(() => {
      result.current.dragProps.onDragEnd({} as unknown as PointerEvent, panInfo(COMMIT_THRESHOLD_PX - 20));
    });
    expect(onDecide).not.toHaveBeenCalled();
  });

  it("does not call onDecide for a vertical-dominant drag, even past the horizontal threshold (axis lock)", () => {
    const onDecide = vi.fn();
    const { result } = renderHook(() => useSwipeToDecide({ onDecide }));

    act(() => {
      result.current.dragProps.onDragEnd(
        {} as unknown as PointerEvent,
        panInfo(COMMIT_THRESHOLD_PX + 5, COMMIT_THRESHOLD_PX + 50),
      );
    });
    expect(onDecide).not.toHaveBeenCalled();
  });

  it("triggerDecision/drag commit are no-ops while disabled", () => {
    const onDecide = vi.fn();
    const { result } = renderHook(() => useSwipeToDecide({ onDecide, disabled: true }));

    act(() => {
      result.current.triggerDecision("interested", "tap");
      result.current.dragProps.onDragEnd(
        {} as unknown as PointerEvent,
        panInfo(COMMIT_THRESHOLD_PX + 5),
      );
    });
    expect(onDecide).not.toHaveBeenCalled();
  });

  /**
   * Adversarial review (TASK 4A REVIEW, SIGNIFICANT finding): the
   * `disabled` guard existed and was unit-tested (above), but nothing
   * ever wired a real "decision in flight" signal through it, so it
   * never actually engaged against a genuine fast double-swipe/
   * double-tap/double-keypress landing before a re-render. Fixed with a
   * synchronous internal `hasDecidedRef` guard (independent of the
   * `disabled` prop's own React-state timing) plus wiring `disabled`
   * itself through `StackScreen`'s new `isDecisionPending` prop
   * (`StackScreen.test.tsx` covers that half).
   */
  describe("re-entrancy: a single instance never commits a second decision", () => {
    it("two rapid triggerDecision calls in the same tick only fire onDecide once", () => {
      const onDecide = vi.fn();
      const { result } = renderHook(() => useSwipeToDecide({ onDecide }));

      act(() => {
        result.current.triggerDecision("interested", "tap");
        result.current.triggerDecision("not_interested", "keyboard");
      });

      expect(onDecide).toHaveBeenCalledTimes(1);
      expect(onDecide).toHaveBeenCalledWith("interested", "tap");
    });

    it("a rapid drag-commit followed by a tap in the same tick only fires onDecide once", () => {
      const onDecide = vi.fn();
      const { result } = renderHook(() => useSwipeToDecide({ onDecide }));

      act(() => {
        result.current.dragProps.onDragEnd(
          {} as unknown as PointerEvent,
          panInfo(COMMIT_THRESHOLD_PX + 5),
        );
        result.current.triggerDecision("not_interested", "tap");
      });

      expect(onDecide).toHaveBeenCalledTimes(1);
      expect(onDecide).toHaveBeenCalledWith("interested", "swipe");
    });

    it("a decision already committed on this instance blocks a later, separate triggerDecision call too", () => {
      const onDecide = vi.fn();
      const { result } = renderHook(() => useSwipeToDecide({ onDecide }));

      act(() => {
        result.current.triggerDecision("interested", "tap");
      });
      expect(onDecide).toHaveBeenCalledTimes(1);

      onDecide.mockClear();
      act(() => {
        result.current.triggerDecision("not_interested", "keyboard");
      });
      expect(onDecide).not.toHaveBeenCalled();
    });
  });
});
