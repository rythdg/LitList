import { afterEach, describe, expect, it, vi } from "vitest";
import { initOfflineSync } from "./offlineSync";
import { useNetworkStore } from "./networkStore";
import { useRetryQueueStore } from "./retryQueueStore";

describe("initOfflineSync (§4.5, §11.5) — bridges real browser events into the stores", () => {
  afterEach(() => {
    useNetworkStore.setState({ isOnline: true });
    useRetryQueueStore.setState({ items: [], isRetrying: false });
  });

  it("flips networkStore to offline/online on the corresponding window events", () => {
    const cleanup = initOfflineSync();
    try {
      window.dispatchEvent(new Event("offline"));
      expect(useNetworkStore.getState().isOnline).toBe(false);

      window.dispatchEvent(new Event("online"));
      expect(useNetworkStore.getState().isOnline).toBe(true);
    } finally {
      cleanup();
    }
  });

  it("§4.5 point 4: automatically drains the retry queue on reconnect", async () => {
    const cleanup = initOfflineSync();
    try {
      const run = vi.fn().mockResolvedValue(undefined);
      useRetryQueueStore.getState().enqueue({ id: "queued-push", label: "Push to Zotero", run });

      window.dispatchEvent(new Event("online"));
      // retryAll() is fire-and-forget from the listener — flush microtasks.
      await Promise.resolve();
      await Promise.resolve();

      expect(run).toHaveBeenCalledTimes(1);
      expect(useRetryQueueStore.getState().items).toHaveLength(0);
    } finally {
      cleanup();
    }
  });

  it("does not touch the retry queue on offline transitions, only online ones", () => {
    const cleanup = initOfflineSync();
    try {
      const run = vi.fn();
      useRetryQueueStore.getState().enqueue({ id: "still-pending", label: "x", run });

      window.dispatchEvent(new Event("offline"));

      expect(run).not.toHaveBeenCalled();
      expect(useRetryQueueStore.getState().items).toHaveLength(1);
    } finally {
      cleanup();
    }
  });

  it("cleanup stops listening", () => {
    const cleanup = initOfflineSync();
    cleanup();

    window.dispatchEvent(new Event("offline"));
    expect(useNetworkStore.getState().isOnline).toBe(true);
  });
});
