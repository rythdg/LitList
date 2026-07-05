import { afterEach, describe, expect, it, vi } from "vitest";
import { useRetryQueueStore } from "./retryQueueStore";

describe("retryQueueStore (§4.5 point 4, §5.5)", () => {
  afterEach(() => {
    useRetryQueueStore.setState({ items: [], isRetrying: false });
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
});
