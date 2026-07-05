/**
 * Drag-to-decide gesture mechanics for the Stack Screen's current card
 * (SPEC.md §5.3, §5.3b, §11.4).
 *
 * This is a reimplementation (in Framer Motion, against this codebase's
 * real state) of the interaction/animation *math* worth keeping from
 * `design/assets/LLPaperCard.dc.html` — axis-lock detection (a drag only
 * commits as a decision when the horizontal offset dominates the
 * vertical one, so a vertical swipe-down/up for the search/saved panels
 * is never mistaken for a decision), a 110px commit threshold, a
 * rotate+translate transform proportional to drag distance, and fading
 * colored overlays keyed to drag progress. Per BuildPlan.md Task 4A's
 * explicit instruction, nothing else is ported from that reference —
 * only this gesture's math.
 *
 * Per SPEC.md §11.4, swipe/tap/keyboard must all call the *same*
 * decision function. This hook is the one place that happens: a real
 * drag past the threshold and a programmatic `triggerDecision` call
 * (wired to the tap buttons / keyboard shortcuts in `StackScreen.tsx`)
 * both run through `commitExit`, which invokes the caller's `onDecide`
 * synchronously (never waiting on the exit animation — §4.6's "swipe
 * immediately, no lag") and then plays the identical exit animation
 * either way, purely as visual feedback. `onDecide` itself is the *real*
 * single decision function (§11.4's PATCH + optimistic update + next-
 * card prefetch), owned one level up by the app-level wiring (`App.tsx`)
 * — this hook only owns the animation, never the network call or the
 * optimistic cache update.
 */
import { useMotionValue, useTransform, useAnimation, type PanInfo } from "framer-motion";
import { useCallback, useRef } from "react";

export type DecisionSource = "swipe" | "tap" | "keyboard";
export type DecisionValue = "interested" | "not_interested";

export interface UseSwipeToDecideOptions {
  onDecide: (decision: DecisionValue, source: DecisionSource) => void;
  /** True while a decision is already in flight for the current card
   *  (e.g. right after a decide-and-advance) — disables further drag
   *  commits/triggers until the next card mounts, so a fast double-swipe
   *  can't fire two decisions for the same paper. */
  disabled?: boolean;
}

/** Drag distance (px) past which a release commits a decision (matches
 * the design reference's 110px threshold). */
export const COMMIT_THRESHOLD_PX = 110;

export function useSwipeToDecide({ onDecide, disabled = false }: UseSwipeToDecideOptions) {
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-300, 0, 300], [-18, 0, 18]);
  const likeOpacity = useTransform(x, [20, COMMIT_THRESHOLD_PX], [0, 1]);
  const nopeOpacity = useTransform(x, [-COMMIT_THRESHOLD_PX, -20], [1, 0]);
  const controls = useAnimation();

  // Synchronous re-entrancy guard, same pattern/reason as
  // `usePlaybackEngine.ts`'s `statusRef`: the caller's `disabled` prop
  // (typically `updateDecision.isPending`, a React state value) hasn't
  // necessarily committed yet between two input events that land in the
  // same tick (two fast keydowns, a double-tap before React re-renders,
  // or a synchronous test firing two triggers back to back) — a plain
  // ref read/written synchronously inside `commitExit` closes that gap
  // regardless of render timing. Reviewer-found regression (adversarial
  // review, "TASK 4A REVIEW"): the `disabled` prop existed and was
  // tested but no caller ever passed it, so this ref is a second,
  // independent layer, not a replacement for wiring `disabled` through.
  const hasDecidedRef = useRef(false);

  const commitExit = useCallback(
    (decision: DecisionValue, source: DecisionSource) => {
      if (hasDecidedRef.current) return;
      hasDecidedRef.current = true;

      // §11.2/§4.6: the decision itself (the optimistic cache update +
      // PATCH + next-card prefetch, owned by the caller's `onDecide`)
      // fires immediately/synchronously — it never waits on the exit
      // animation, matching "swipe immediately, no lag." The exit
      // animation plays concurrently, purely visual.
      onDecide(decision, source);

      const exitX = decision === "interested" ? 600 : -600;
      const exitRotate = decision === "interested" ? 24 : -24;
      void controls
        .start({
          x: exitX,
          rotate: exitRotate,
          opacity: 0,
          transition: { duration: 0.22, ease: "easeIn" },
        })
        .then(() => {
          // Reset for the next card. Framer Motion's `useAnimation`
          // controls are imperative, so this runs after the exit
          // animation finishes — the parent is expected to remount this
          // card (a new `key`) between papers per §5.3b, but resetting
          // defensively here means a non-remounted reuse still starts
          // from a clean, centered state.
          x.set(0);
          controls.set({ x: 0, rotate: 0, opacity: 1 });
        });
    },
    [controls, onDecide, x],
  );

  const handleDragEnd = useCallback(
    (_event: PointerEvent | MouseEvent | TouchEvent, info: PanInfo) => {
      if (disabled || hasDecidedRef.current) return;
      const { offset } = info;
      const isHorizontalDominant = Math.abs(offset.x) > Math.abs(offset.y);
      if (isHorizontalDominant && Math.abs(offset.x) >= COMMIT_THRESHOLD_PX) {
        void commitExit(offset.x > 0 ? "interested" : "not_interested", "swipe");
        return;
      }
      // Below threshold (or a vertical-dominant drag, e.g. reaching for
      // the search/saved panels) — snap back to center, no decision.
      void controls.start({
        x: 0,
        rotate: 0,
        transition: { type: "spring", stiffness: 500, damping: 32 },
      });
    },
    [commitExit, controls, disabled],
  );

  /** Called by the tap buttons / keyboard shortcuts (`StackScreen.tsx`)
   * — plays the exact same exit animation a completed swipe would, then
   * calls the same `onDecide`. This is what makes swipe/tap/keyboard
   * three triggers into one function, per §11.4. */
  const triggerDecision = useCallback(
    (decision: DecisionValue, source: Exclude<DecisionSource, "swipe">) => {
      if (disabled || hasDecidedRef.current) return;
      void commitExit(decision, source);
    },
    [commitExit, disabled],
  );

  return {
    x,
    rotate,
    likeOpacity,
    nopeOpacity,
    controls,
    dragProps: {
      drag: "x" as const,
      dragConstraints: { left: 0, right: 0 },
      dragElastic: 1,
      onDragEnd: handleDragEnd,
    },
    triggerDecision,
  };
}
