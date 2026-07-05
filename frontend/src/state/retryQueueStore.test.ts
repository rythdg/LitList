import { afterEach, describe, expect, it, vi } from "vitest";
import { PermanentRetryFailure, useRetryQueueStore } from "./retryQueueStore";

describe("retryQueueStore (§4.5 point 4, §5.5)", () => {
  afterEach(() => {
    useRetryQueueStore.setState({ items: [], failedItems: [], isRetrying: false });
  });

  it("enqueues an item and removes it once retryAll succeeds", async () => {
    const run = vi.fn().mockResolvedValue(undefined);
    useRetryQueueStore.getState().enqueue({ id: "a", label: "Push to Zotero", run });

    expect(useRetryQueueStore.getState().items).toHaveLength(1);

    await useRetryQueueStore.getState().retryAll();

    expect(run).toHaveBeenCalledTimes(1);
    expect(useRetryQueueStore.getState().items).toHaveLength(0);
  });

  it("leaves a failed item queued for the next retry pass rather than dropping it", async () => {
    const run = vi.fn().mockRejectedValue(new Error("still offline"));
    useRetryQueueStore.getState().enqueue({ id: "b", label: "Save decision", run });

    await useRetryQueueStore.getState().retryAll();

    expect(run).toHaveBeenCalledTimes(1);
    expect(useRetryQueueStore.getState().items).toHaveLength(1);
    expect(useRetryQueueStore.getState().isRetrying).toBe(false);
  });

  it("re-enqueuing with the same id replaces rather than duplicates", () => {
    const runA = vi.fn();
    const runB = vi.fn();
    useRetryQueueStore.getState().enqueue({ id: "c", label: "first", run: runA });
    useRetryQueueStore.getState().enqueue({ id: "c", label: "second", run: runB });

    const items = useRetryQueueStore.getState().items;
    expect(items).toHaveLength(1);
    expect(items[0].label).toBe("second");
  });

  it("remove() drops a specific pending item without affecting others", () => {
    useRetryQueueStore.getState().enqueue({ id: "d1", label: "one", run: vi.fn() });
    useRetryQueueStore.getState().enqueue({ id: "d2", label: "two", run: vi.fn() });

    useRetryQueueStore.getState().remove("d1");

    const items = useRetryQueueStore.getState().items;
    expect(items).toHaveLength(1);
    expect(items[0].id).toBe("d2");
  });

  it("retryAll() is a no-op with an empty queue", async () => {
    await expect(useRetryQueueStore.getState().retryAll()).resolves.toBeUndefined();
  });

  it("adversarial review Finding 1: a PermanentRetryFailure on retry stops the item from being retried forever and surfaces it as failed instead", async () => {
    const run = vi.fn().mockRejectedValue(new PermanentRetryFailure("Decision not found."));
    useRetryQueueStore.getState().enqueue({ id: "e", label: "Save decision for paper X", run });

    await useRetryQueueStore.getState().retryAll();

    // Removed from the pending queue — not stuck in an invisible
    // infinite retry loop the way an undifferentiated `catch {}` would
    // leave it.
    expect(useRetryQueueStore.getState().items).toHaveLength(0);
    // Surfaced, not silently dropped.
    expect(useRetryQueueStore.getState().failedItems).toEqual([
      { id: "e", label: "Save decision for paper X", message: "Decision not found." },
    ]);

    // A second retryAll() pass (e.g. the next `online` event) doesn't
    // call `run()` again — it's no longer in the queue at all.
    await useRetryQueueStore.getState().retryAll();
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("a transient (non-PermanentRetryFailure) rejection on retry still stays queued rather than being treated as a permanent failure", async () => {
    const run = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    useRetryQueueStore.getState().enqueue({ id: "f", label: "Save decision for paper Y", run });

    await useRetryQueueStore.getState().retryAll();

    expect(useRetryQueueStore.getState().items).toHaveLength(1);
    expect(useRetryQueueStore.getState().failedItems).toHaveLength(0);
  });

  it("dismissFailed() drops a specific failed item without affecting others", async () => {
    useRetryQueueStore.setState({
      items: [],
      failedItems: [
        { id: "g1", label: "one", message: "nope" },
        { id: "g2", label: "two", message: "nope" },
      ],
      isRetrying: false,
    });

    useRetryQueueStore.getState().dismissFailed("g1");

    expect(useRetryQueueStore.getState().failedItems).toEqual([
      { id: "g2", label: "two", message: "nope" },
    ]);
  });
});
