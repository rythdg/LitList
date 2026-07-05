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
  run: () => Promise<void>;
}

export interface RetryQueueState {
  items: RetryQueueItem[];
  /** True while a `retryAll()` pass is in flight, so UI can avoid firing
   *  a second overlapping retry pass (e.g. both the `online` event and a
   *  manual "Retry now" click landing at once). */
  isRetrying: boolean;
  enqueue: (item: RetryQueueItem) => void;
  remove: (id: string) => void;
  /** Attempts every queued item once, in order. Items whose `run()`
   *  resolves are removed; items whose `run()` rejects stay queued for
   *  the next attempt (next reconnect, or the next manual retry). Never
   *  throws — a failed item is just left pending. */
  retryAll: () => Promise<void>;
}

export const useRetryQueueStore = create<RetryQueueState>((set, get) => ({
  items: [],
  isRetrying: false,

  enqueue: (item) =>
    set((state) => ({
      // Replacing an item with the same id (e.g. re-enqueuing after an
      // edit) rather than piling up duplicates.
      items: [...state.items.filter((existing) => existing.id !== item.id), item],
    })),

  remove: (id) =>
    set((state) => ({ items: state.items.filter((item) => item.id !== id) })),

  retryAll: async () => {
    const { isRetrying, items } = get();
    if (isRetrying || items.length === 0) return;

    set({ isRetrying: true });
    try {
      for (const item of items) {
        try {
          await item.run();
          set((state) => ({ items: state.items.filter((i) => i.id !== item.id) }));
        } catch {
          // Left in the queue deliberately — no error is surfaced from
          // here; the originating screen's own error state (ErrorState)
          // is what the user sees, not this background drain.
        }
      }
    } finally {
      set({ isRetrying: false });
    }
  },
}));
