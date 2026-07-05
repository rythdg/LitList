import { create } from "zustand";

/**
 * "Pending — will retry" queue (SPEC.md §4.5 point 4, §5.5's Step 2
 * offline variant). Any action attempted while offline (a decision PATCH,
 * a Zotero push, etc.) can be handed to this queue via `enqueue` instead
 * of failing silently or being lost — `offlineSync.ts` drains it
 * automatically on the browser's `online` event, and any screen can also
 * offer a manual "Retry now" affordance that calls `retryAll` directly
 * (§5.5's Step 3b "Retry" button, §5.5's Step 2 pending variant).
 *
 * This store is intentionally generic (an opaque `run: () => Promise<void>`
 * per item) — it does not know about decisions, Zotero, or any specific
 * endpoint. Task 4A/4B wire their own real retryable actions into this
 * queue; this task only builds the mechanism itself.
 */
export interface RetryQueueItem {
  /** Stable id so a caller can `remove` a specific pending action (e.g.
   *  the user manually undoes/replaces it) without draining the whole
   *  queue. */
  id: string;
  /** Short, user-facing description of what's pending, for a "Pending —
   *  will retry" UI (§5.5) — e.g. "Push 7 papers to Zotero". */
  label: string;
  /** Reject with a plain `Error` (or let a genuine network-level
   *  rejection like `TypeError: Failed to fetch` propagate) for a
   *  *transient* failure — the item stays queued for the next attempt.
   *  Reject with `PermanentRetryFailure` for a failure that retrying
   *  again, unchanged, cannot fix (a real server-side rejection, not a
   *  connectivity problem) — the item is removed from the retry queue
   *  and surfaced via `failedItems` instead of being retried forever.
   *  This store deliberately stays agnostic of *why* something is
   *  permanent (it never imports `ApiError`/CONTRACTS.md's shape) —
   *  translating a domain-specific error into this generic marker is
   *  each producer's own job (see `api/decisions.ts`). */
  run: () => Promise<void>;
}

/** SIGNIFICANT-finding fix (adversarial review, "TASK 4C SEC15.6
 *  FOLLOW-UP REVIEW", Finding 1): a plain marker class so `retryAll()`
 *  can tell "this needs a network to come back" apart from "this will
 *  never succeed by retrying the exact same request again" without the
 *  generic queue mechanism needing to know about any specific producer's
 *  error shape. */
export class PermanentRetryFailure extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PermanentRetryFailure";
  }
}

/** A queued item that gave up for good (Finding 1) — surfaced (Finding
 *  2) so a real failure doesn't sit in `items` forever silently
 *  indistinguishable from a still-pending one, nor vanish without a
 *  trace the way an unconditional `catch {}` would. */
export interface FailedRetryItem {
  id: string;
  label: string;
  message: string;
}

export interface RetryQueueState {
  items: RetryQueueItem[];
  /** Finding 2: items that permanently failed and are no longer being
   *  retried — a screen can render these (e.g. "Couldn't save: <label>")
   *  and let the user `dismissFailed` them. */
  failedItems: FailedRetryItem[];
  /** True while a `retryAll()` pass is in flight, so UI can avoid firing
   *  a second overlapping retry pass (e.g. both the `online` event and a
   *  manual "Retry now" click landing at once). */
  isRetrying: boolean;
  enqueue: (item: RetryQueueItem) => void;
  /** Removes a still-pending item outright (e.g. the user manually
   *  undoes/replaces it) — NOT what a permanent failure uses; that path
   *  goes through `retryAll()`'s own bookkeeping into `failedItems`
   *  instead, so a caller reaching for "get rid of this" during normal
   *  operation can't accidentally erase a failure without it ever being
   *  surfaced. Note for future producers (adversarial review's
   *  informational note): if more than one producer ever calls
   *  `retryAll()` concurrently, this id-based removal inside the
   *  `for`-loop below assumes item identity is stable across the whole
   *  pass — not currently reachable with `retryAll()`'s own single-flight
   *  `isRetrying` guard plus today's single producer, but worth
   *  revisiting if that changes. */
  remove: (id: string) => void;
  dismissFailed: (id: string) => void;
  /** Attempts every queued item once, in order. Items whose `run()`
   *  resolves are removed; items whose `run()` rejects with a plain
   *  error stay queued for the next attempt (next reconnect, or the
   *  next manual retry); items whose `run()` rejects with
   *  `PermanentRetryFailure` are removed from `items` and moved into
   *  `failedItems` instead of being retried forever (Finding 1). Never
   *  throws itself either way. */
  retryAll: () => Promise<void>;
}

export const useRetryQueueStore = create<RetryQueueState>((set, get) => ({
  items: [],
  failedItems: [],
  isRetrying: false,

  enqueue: (item) =>
    set((state) => ({
      // Replacing an item with the same id (e.g. re-enqueuing after an
      // edit) rather than piling up duplicates.
      items: [...state.items.filter((existing) => existing.id !== item.id), item],
    })),

  remove: (id) =>
    set((state) => ({ items: state.items.filter((item) => item.id !== id) })),

  dismissFailed: (id) =>
    set((state) => ({ failedItems: state.failedItems.filter((item) => item.id !== id) })),

  retryAll: async () => {
    const { isRetrying, items } = get();
    if (isRetrying || items.length === 0) return;

    set({ isRetrying: true });
    try {
      for (const item of items) {
        try {
          await item.run();
          set((state) => ({ items: state.items.filter((i) => i.id !== item.id) }));
        } catch (error) {
          if (error instanceof PermanentRetryFailure) {
            set((state) => ({
              items: state.items.filter((i) => i.id !== item.id),
              failedItems: [
                ...state.failedItems.filter((f) => f.id !== item.id),
                { id: item.id, label: item.label, message: error.message },
              ],
            }));
          }
          // Any other rejection (a genuine network-level failure) is
          // left in the queue deliberately for the next attempt — no
          // error is surfaced from here for that case; the originating
          // screen's own error state (ErrorState) is what the user sees
          // for *that* failure, not this background drain.
        }
      }
    } finally {
      set({ isRetrying: false });
    }
  },
}));
