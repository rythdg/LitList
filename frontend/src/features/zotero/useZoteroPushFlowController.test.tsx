import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API_BASE_URL } from "../../api/client";
import {
  FIXTURE_ZOTERO_COLLECTIONS_RESPONSE,
  FIXTURE_ZOTERO_NOT_CONNECTED_ERROR,
} from "../../api/mocks/fixtures";
import { server } from "../../api/mocks/server";
import { createTestQueryClient, wrapperWithClient } from "../../api/testUtils";
import { useNetworkStore } from "../../state/networkStore";
import { useZoteroPushFlowStore } from "../../state/zoteroPushFlowStore";
import { useZoteroPushFlowController } from "./useZoteroPushFlowController";

/**
 * Task 4B — the three scenarios called out by BuildPlan.md's own test
 * brief for this task (§15.3/§15.7): success, connection failure, and
 * push (partial) failure, all driven against MSW-mocked real endpoints
 * (`GET/POST /zotero/collections`, `POST /zotero/push`) rather than a
 * hand-rolled mock of this hook's own logic.
 */
describe("useZoteroPushFlowController (§5.5, ties 2B's ZoteroPushFlow to 3B's routes)", () => {
  const onClose = vi.fn();

  beforeEach(() => {
    onClose.mockReset();
    useNetworkStore.setState({ isOnline: true });
    useZoteroPushFlowStore.setState({ isPushPending: false });
  });

  afterEach(() => {
    useNetworkStore.setState({ isOnline: true });
    useZoteroPushFlowStore.setState({ isPushPending: false });
  });

  it("Step 1: shows the connect step when there is no ZoteroConnection", async () => {
    server.use(
      http.get(`${API_BASE_URL}/zotero/collections`, () =>
        HttpResponse.json(FIXTURE_ZOTERO_NOT_CONNECTED_ERROR, { status: 401 }),
      ),
    );
    const client = createTestQueryClient();
    const { result } = renderHook(
      () => useZoteroPushFlowController({ pmids: ["38279812"], onClose }),
      { wrapper: wrapperWithClient(client) },
    );

    await waitFor(() => expect(result.current.step).toBe("connect"));
  });

  it("Step 1: onConnect does a real full-page navigation to /zotero/auth/start, never a fetch", async () => {
    server.use(
      http.get(`${API_BASE_URL}/zotero/collections`, () =>
        HttpResponse.json(FIXTURE_ZOTERO_NOT_CONNECTED_ERROR, { status: 401 }),
      ),
    );
    const client = createTestQueryClient();
    const { result } = renderHook(
      () => useZoteroPushFlowController({ pmids: ["38279812"], onClose }),
      { wrapper: wrapperWithClient(client) },
    );
    await waitFor(() => expect(result.current.step).toBe("connect"));

    // jsdom doesn't implement real cross-document navigation, so a bare
    // `window.location.href = ...` assignment logs "Not implemented" and
    // leaves `window.location` unchanged rather than being observable —
    // stub `location` with a plain writable object for this one
    // assertion instead.
    const originalLocation = window.location;
    const stub = { href: "" } as unknown as Location;
    Object.defineProperty(window, "location", { value: stub, writable: true });

    act(() => {
      result.current.onConnect();
    });
    expect(stub.href).toBe(`${API_BASE_URL}/zotero/auth/start`);

    Object.defineProperty(window, "location", { value: originalLocation, writable: true });
  });

  it("Step 2: lists real collections once connected", async () => {
    const client = createTestQueryClient();
    const { result } = renderHook(
      () => useZoteroPushFlowController({ pmids: ["38279812"], onClose }),
      { wrapper: wrapperWithClient(client) },
    );

    await waitFor(() => expect(result.current.step).toBe("choose_collection"));
    expect(result.current.collections).toEqual(FIXTURE_ZOTERO_COLLECTIONS_RESPONSE.collections);
  });

  it("Step 2 offline: isOffline mirrors the shared networkStore, not a locally re-derived signal", async () => {
    useNetworkStore.setState({ isOnline: false });
    const client = createTestQueryClient();
    const { result } = renderHook(
      () => useZoteroPushFlowController({ pmids: ["38279812"], onClose }),
      { wrapper: wrapperWithClient(client) },
    );

    await waitFor(() => expect(result.current.step).toBe("choose_collection"));
    expect(result.current.isOffline).toBe(true);
  });

  it("Step 3a: all-success push moves to the success step", async () => {
    server.use(
      http.post(`${API_BASE_URL}/zotero/push`, () =>
        HttpResponse.json({
          collection_key: "ABCD1234",
          results: [{ pmid: "38279812", status: "success", zotero_item_key: "XJ2K9F3P" }],
        }),
      ),
    );
    const client = createTestQueryClient();
    const { result } = renderHook(
      () => useZoteroPushFlowController({ pmids: ["38279812"], onClose }),
      { wrapper: wrapperWithClient(client) },
    );
    await waitFor(() => expect(result.current.step).toBe("choose_collection"));

    act(() => result.current.onSelectCollection("ABCD1234"));
    act(() => result.current.onSave());

    await waitFor(() => expect(result.current.step).toBe("success"));
  });

  it("Step 3b (push failure, CONTRACTS.md §3): a per-PMID failure in an otherwise-200 response routes to failure/push, and Retry only resubmits the failed PMID", async () => {
    let pushCallCount = 0;
    let lastRequestedPmids: string[] = [];
    server.use(
      http.post(`${API_BASE_URL}/zotero/push`, async ({ request }) => {
        pushCallCount += 1;
        const body = (await request.json()) as { pmids: string[] };
        lastRequestedPmids = body.pmids;
        return HttpResponse.json({
          collection_key: "ABCD1234",
          results: body.pmids.map((pmid, index) =>
            index === 0
              ? { pmid, status: "success" as const, zotero_item_key: "XJ2K9F3P" }
              : {
                  pmid,
                  status: "failure" as const,
                  error: { code: "service_unavailable", message: "Zotero is currently unavailable." },
                },
          ),
        });
      }),
    );
    const client = createTestQueryClient();
    const { result } = renderHook(
      () =>
        useZoteroPushFlowController({ pmids: ["38279812", "38279813"], onClose }),
      { wrapper: wrapperWithClient(client) },
    );
    await waitFor(() => expect(result.current.step).toBe("choose_collection"));

    act(() => result.current.onSelectCollection("ABCD1234"));
    act(() => result.current.onSave());

    await waitFor(() => expect(result.current.step).toBe("failure"));
    expect(result.current.failureReason).toBe("push");
    expect(pushCallCount).toBe(1);
    expect(lastRequestedPmids).toEqual(["38279812", "38279813"]);

    // Retry (§8.7): only the PMID that actually failed is resubmitted —
    // never an all-or-nothing resend of the whole saved list.
    act(() => result.current.onRetry());
    await waitFor(() => expect(pushCallCount).toBe(2));
    expect(lastRequestedPmids).toEqual(["38279813"]);
  });

  it("Step 3b (connection failure): the push request itself failing (not a per-item result) routes to failure/connection", async () => {
    server.use(
      http.post(`${API_BASE_URL}/zotero/push`, () =>
        HttpResponse.json(
          { error: { code: "service_unavailable", message: "Zotero is currently unavailable." } },
          { status: 503 },
        ),
      ),
    );
    const client = createTestQueryClient();
    const { result } = renderHook(
      () => useZoteroPushFlowController({ pmids: ["38279812"], onClose }),
      { wrapper: wrapperWithClient(client) },
    );
    await waitFor(() => expect(result.current.step).toBe("choose_collection"));

    act(() => result.current.onSelectCollection("ABCD1234"));
    act(() => result.current.onSave());

    await waitFor(() => expect(result.current.step).toBe("failure"));
    expect(result.current.failureReason).toBe("connection");
  });

  it("onCancel/onDone both call the caller's onClose", async () => {
    const client = createTestQueryClient();
    const { result } = renderHook(
      () => useZoteroPushFlowController({ pmids: ["38279812"], onClose }),
      { wrapper: wrapperWithClient(client) },
    );
    await waitFor(() => expect(result.current.step).toBe("choose_collection"));

    act(() => result.current.onCancel());
    expect(onClose).toHaveBeenCalledTimes(1);
    act(() => result.current.onDone());
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  describe("post-review fixes (adversarial-generalist \"TASK 4B REVIEW\")", () => {
    /** Holds a `POST /zotero/push` response open until the test resolves
     *  it, so assertions can observe the in-flight state (`isSaving`,
     *  the shared store's `isPushPending`) before the mutation settles —
     *  the same technique used to reproduce/guard against a rapid
     *  double-click racing a real network round-trip. */
    function deferredPushHandler() {
      let resolve!: (value: { collection_key: string; results: unknown[] }) => void;
      const promise = new Promise<{ collection_key: string; results: unknown[] }>((res) => {
        resolve = res;
      });
      let callCount = 0;
      server.use(
        http.post(`${API_BASE_URL}/zotero/push`, async ({ request }) => {
          callCount += 1;
          const body = (await request.json()) as { collection_key: string; pmids: string[] };
          const result = await promise;
          return HttpResponse.json({
            collection_key: body.collection_key,
            results: result.results.length
              ? result.results
              : body.pmids.map((pmid) => ({ pmid, status: "success" as const, zotero_item_key: `K-${pmid}` })),
          });
        }),
      );
      return { resolve: () => resolve({ collection_key: "ABCD1234", results: [] }), getCallCount: () => callCount };
    }

    it("finding #1: a rapid double-call of onSave never fires two concurrent pushes", async () => {
      const { resolve, getCallCount } = deferredPushHandler();
      const client = createTestQueryClient();
      const { result } = renderHook(
        () => useZoteroPushFlowController({ pmids: ["38279812"], onClose }),
        { wrapper: wrapperWithClient(client) },
      );
      await waitFor(() => expect(result.current.step).toBe("choose_collection"));
      act(() => result.current.onSelectCollection("ABCD1234"));

      // Two synchronous calls in the same tick, exactly like a fast
      // double-click before React/TanStack Query has had a chance to
      // reflect the first mutation's pending state anywhere else.
      act(() => {
        result.current.onSave();
        result.current.onSave();
      });
      await waitFor(() => expect(result.current.isSaving).toBe(true));
      expect(getCallCount()).toBe(1);

      // A third call while still pending (e.g. Retry clicked before Save
      // resolves) must also be a no-op, not a second request.
      act(() => result.current.onRetry());
      expect(getCallCount()).toBe(1);

      resolve();
      await waitFor(() => expect(result.current.step).toBe("success"));
      expect(getCallCount()).toBe(1);
    });

    it("finding #1: isSaving mirrors push.isPending, driving ZoteroPushFlow's Save/Retry disabled state", async () => {
      const { resolve } = deferredPushHandler();
      const client = createTestQueryClient();
      const { result } = renderHook(
        () => useZoteroPushFlowController({ pmids: ["38279812"], onClose }),
        { wrapper: wrapperWithClient(client) },
      );
      await waitFor(() => expect(result.current.step).toBe("choose_collection"));
      expect(result.current.isSaving).toBe(false);

      act(() => result.current.onSelectCollection("ABCD1234"));
      act(() => result.current.onSave());
      await waitFor(() => expect(result.current.isSaving).toBe(true));

      resolve();
      await waitFor(() => expect(result.current.isSaving).toBe(false));
    });

    it("finding #2: onCancel is a no-op while a push is in flight, and works again once it settles", async () => {
      const { resolve } = deferredPushHandler();
      const client = createTestQueryClient();
      const { result } = renderHook(
        () => useZoteroPushFlowController({ pmids: ["38279812"], onClose }),
        { wrapper: wrapperWithClient(client) },
      );
      await waitFor(() => expect(result.current.step).toBe("choose_collection"));

      act(() => result.current.onSelectCollection("ABCD1234"));
      act(() => result.current.onSave());
      await waitFor(() => expect(result.current.isSaving).toBe(true));

      act(() => result.current.onCancel());
      expect(onClose).not.toHaveBeenCalled();

      resolve();
      await waitFor(() => expect(result.current.isSaving).toBe(false));
      act(() => result.current.onCancel());
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it("finding #2: mirrors push.isPending into the shared zoteroPushFlowStore, so surfaces outside this flow (Disconnect Zotero) can guard against it", async () => {
      const { resolve } = deferredPushHandler();
      const client = createTestQueryClient();
      const { result } = renderHook(
        () => useZoteroPushFlowController({ pmids: ["38279812"], onClose }),
        { wrapper: wrapperWithClient(client) },
      );
      await waitFor(() => expect(result.current.step).toBe("choose_collection"));
      expect(useZoteroPushFlowStore.getState().isPushPending).toBe(false);

      act(() => result.current.onSelectCollection("ABCD1234"));
      act(() => result.current.onSave());
      await waitFor(() => expect(useZoteroPushFlowStore.getState().isPushPending).toBe(true));

      resolve();
      await waitFor(() => expect(useZoteroPushFlowStore.getState().isPushPending).toBe(false));
    });
  });
});
