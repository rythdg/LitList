import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useRunSearch, useSearchSettings } from "./search";
import { useQueue } from "./queue";
import { FIXTURE_QUEUE_RESPONSE } from "./mocks/fixtures";
import { createTestQueryClient, wrapperWithClient } from "./testUtils";

describe("useSearchSettings / useRunSearch (§10.4 /search, /search/settings, §3.5)", () => {
  it("returns pre-fill settings", async () => {
    const client = createTestQueryClient();
    const { result } = renderHook(() => useSearchSettings(), { wrapper: wrapperWithClient(client) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.sort).toBe("relevance");
  });

  it("seeds the queue cache directly on a successful search, without a separate refetch", async () => {
    const client = createTestQueryClient();
    const wrapper = wrapperWithClient(client);

    const { result: queueResult } = renderHook(() => useQueue(), { wrapper });
    const { result: searchResult } = renderHook(() => useRunSearch(), { wrapper });

    await act(async () => {
      await searchResult.current.mutateAsync({
        query: "spiking neural networks",
        sort: "relevance",
        read_aloud_fields: ["journal"],
        default_swipe_behavior: "not_interested",
        speed: 1,
      });
    });

    await waitFor(() => expect(queueResult.current.data).toEqual(FIXTURE_QUEUE_RESPONSE));
  });
});
