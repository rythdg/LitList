import { renderHook, waitFor, act } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { API_BASE_URL } from "./client";
import { useQueue } from "./queue";
import { useUpdateDecision } from "./decisions";
import { server } from "./mocks/server";
import { createTestQueryClient, wrapperWithClient } from "./testUtils";
import { useRetryQueueStore } from "../state/retryQueueStore";

describe("useUpdateDecision (§10.4 PATCH /decisions/{pmid}, §11.2 optimistic update)", () => {
  beforeEach(() => {
    useRetryQueueStore.setState({ items: [], failedItems: [], isRetrying: false });
  });

  it("optimistically updates the queue cache before the server responds", async () => {
    const client = createTestQueryClient();
    const wrapper = wrapperWithClient(client);

    // Delay the server response so we can observe the optimistic state
    // in between mutate() and the request resolving.
    server.use(
      http.patch(`${API_BASE_URL}/decisions/:pmid`, async () => {
        await new Promise((r) => setTimeout(r, 50));
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const { result: queueResult } = renderHook(() => useQueue(), { wrapper });
    await waitFor(() => expect(queueResult.current.isSuccess).toBe(true));

    const { result: decisionResult } = renderHook(() => useUpdateDecision(), { wrapper });

    act(() => {
      decisionResult.current.mutate({ pmid: "38279812", decision: "interested", decided_via: "swipe" });
    });

    await waitFor(() => {
      const item = queueResult.current.data?.items.find((i) => i.pmid === "38279812");
      expect(item?.decision).toBe("interested");
    });

    await waitFor(() => expect(decisionResult.current.isSuccess).toBe(true));
  });

  it("rolls back the optimistic update if the PATCH fails", async () => {
    const client = createTestQueryClient();
    const wrapper = wrapperWithClient(client);

    server.use(
      http.patch(`${API_BASE_URL}/decisions/:pmid`, () =>
        HttpResponse.json({ error: { code: "not_found", message: "Decision not found." } }, { status: 404 }),
      ),
    );

    const { result: queueResult } = renderHook(() => useQueue(), { wrapper });
    await waitFor(() => expect(queueResult.current.isSuccess).toBe(true));

    const { result: decisionResult } = renderHook(() => useUpdateDecision(), { wrapper });

    act(() => {
      decisionResult.current.mutate({ pmid: "38279812", decision: "not_interested", decided_via: "swipe" });
    });

    await waitFor(() => expect(decisionResult.current.isError).toBe(true));

    const item = queueResult.current.data?.items.find((i) => i.pmid === "38279812");
    expect(item?.decision).toBe("pending");
  });

  it("§4.5: a network-level failure (fetch itself rejects, no ApiError) keeps the optimistic decision and queues it in retryQueueStore instead of rolling back", async () => {
    const client = createTestQueryClient();
    const wrapper = wrapperWithClient(client);

    // `HttpResponse.error()` makes MSW simulate a network error — the
    // request never reaches a server, so `apiFetch` never constructs an
    // `ApiError`; this is what a real offline `fetch()` rejection looks
    // like, distinct from the 404 case above.
    server.use(http.patch(`${API_BASE_URL}/decisions/:pmid`, () => HttpResponse.error()));

    const { result } = renderHook(() => ({ queue: useQueue(), decision: useUpdateDecision() }), { wrapper });
    await waitFor(() => expect(result.current.queue.isSuccess).toBe(true));

    act(() => {
      result.current.decision.mutate({ pmid: "38279812", decision: "interested", decided_via: "swipe" });
    });

    await waitFor(() => expect(result.current.decision.isError).toBe(true));

    // Not rolled back — the optimistic decision is kept.
    await waitFor(() => {
      const item = result.current.queue.data?.items.find((i) => i.pmid === "38279812");
      expect(item?.decision).toBe("interested");
    });

    // Queued for retry under a stable, pmid-scoped id.
    expect(useRetryQueueStore.getState().items.map((i) => i.id)).toContain("decision-38279812");
  });

  it("§4.5 point 4: the queued decision is actually replayed and succeeds once retryQueueStore.retryAll() runs (the real reconnect path, not a mock)", async () => {
    const client = createTestQueryClient();
    const wrapper = wrapperWithClient(client);

    let patchCount = 0;
    server.use(
      http.patch(`${API_BASE_URL}/decisions/:pmid`, () => {
        patchCount += 1;
        return patchCount === 1 ? HttpResponse.error() : new HttpResponse(null, { status: 204 });
      }),
    );

    const { result: queueResult } = renderHook(() => useQueue(), { wrapper });
    await waitFor(() => expect(queueResult.current.isSuccess).toBe(true));

    const { result: decisionResult } = renderHook(() => useUpdateDecision(), { wrapper });

    act(() => {
      decisionResult.current.mutate({ pmid: "38279812", decision: "interested", decided_via: "swipe" });
    });

    await waitFor(() => expect(decisionResult.current.isError).toBe(true));
    expect(useRetryQueueStore.getState().items).toHaveLength(1);

    // The same mechanism `offlineSync.ts`'s real `online` listener calls
    // on reconnect — exercised directly here, not stubbed.
    await act(async () => {
      await useRetryQueueStore.getState().retryAll();
    });

    expect(patchCount).toBe(2);
    expect(useRetryQueueStore.getState().items).toHaveLength(0);
  });

  it("adversarial review Finding 1: a real ApiError on the *retried* attempt stops it from being retried forever and surfaces it as a real failure", async () => {
    const client = createTestQueryClient();
    const wrapper = wrapperWithClient(client);

    // First attempt: a genuine network-level failure (queues it, as the
    // test above already proves). By the time reconnect replays it,
    // something has genuinely changed server-side (session expired, the
    // paper no longer exists, etc.) — the retried request now gets a
    // real `ApiError` (404), not another network drop.
    let patchCount = 0;
    server.use(
      http.patch(`${API_BASE_URL}/decisions/:pmid`, () => {
        patchCount += 1;
        return patchCount === 1
          ? HttpResponse.error()
          : HttpResponse.json({ error: { code: "not_found", message: "Decision not found." } }, { status: 404 });
      }),
    );

    const { result: decisionResult } = renderHook(() => useUpdateDecision(), { wrapper });

    act(() => {
      decisionResult.current.mutate({ pmid: "38279812", decision: "interested", decided_via: "swipe" });
    });

    await waitFor(() => expect(decisionResult.current.isError).toBe(true));
    expect(useRetryQueueStore.getState().items).toHaveLength(1);

    await act(async () => {
      await useRetryQueueStore.getState().retryAll();
    });

    expect(patchCount).toBe(2);
    // Not stuck retrying forever...
    expect(useRetryQueueStore.getState().items).toHaveLength(0);
    // ...and not silently dropped either — surfaced as a real failure.
    expect(useRetryQueueStore.getState().failedItems).toEqual([
      { id: "decision-38279812", label: "Save decision for paper 38279812", message: "Decision not found." },
    ]);

    // A subsequent retryAll() pass (the next `online` event) doesn't
    // attempt this request a third time — it's no longer queued at all.
    await act(async () => {
      await useRetryQueueStore.getState().retryAll();
    });
    expect(patchCount).toBe(2);
  });
});
