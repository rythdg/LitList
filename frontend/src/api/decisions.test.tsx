import { renderHook, waitFor, act } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { API_BASE_URL } from "./client";
import { useQueue } from "./queue";
import { useUpdateDecision } from "./decisions";
import { server } from "./mocks/server";
import { createTestQueryClient, wrapperWithClient } from "./testUtils";

describe("useUpdateDecision (§10.4 PATCH /decisions/{pmid}, §11.2 optimistic update)", () => {
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
      const item = queueResult.current.data?.items.find((i) => i.paper.pmid === "38279812");
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

    const item = queueResult.current.data?.items.find((i) => i.paper.pmid === "38279812");
    expect(item?.decision).toBe("pending");
  });
});
