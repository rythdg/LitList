import { renderHook, waitFor, act } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { API_BASE_URL } from "./client";
import { useSaved, useRemoveSaved } from "./saved";
import { FIXTURE_SAVED_RESPONSE } from "./mocks/fixtures";
import { server } from "./mocks/server";
import { createTestQueryClient, wrapperWithClient } from "./testUtils";

describe("useSaved / useRemoveSaved (§10.4 GET/DELETE /saved, §4.7)", () => {
  it("returns the MSW-mocked saved-list fixture", async () => {
    const client = createTestQueryClient();
    const { result } = renderHook(() => useSaved(), { wrapper: wrapperWithClient(client) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(FIXTURE_SAVED_RESPONSE);
  });

  it("optimistically removes the item from the saved-list cache on DELETE", async () => {
    const client = createTestQueryClient();
    const wrapper = wrapperWithClient(client);

    // Delay the server response so the optimistic (pre-invalidation)
    // state is observable rather than immediately overwritten by the
    // onSettled refetch of the (static) fixture.
    server.use(
      http.delete(`${API_BASE_URL}/saved/:pmid`, async () => {
        await new Promise((r) => setTimeout(r, 50));
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const { result: savedResult } = renderHook(() => useSaved(), { wrapper });
    await waitFor(() => expect(savedResult.current.isSuccess).toBe(true));
    expect(savedResult.current.data?.items).toHaveLength(1);

    const { result: removeResult } = renderHook(() => useRemoveSaved(), { wrapper });
    act(() => {
      removeResult.current.mutate("38279812");
    });

    await waitFor(() => expect(savedResult.current.data?.items).toHaveLength(0));
  });
});
