import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useAbstract } from "./abstract";
import { FIXTURE_ABSTRACT_RESPONSE } from "./mocks/fixtures";
import { createTestQueryClient, wrapperWithClient } from "./testUtils";

describe("useAbstract (§10.4 GET /papers/{pmid}/abstract, CONTRACTS.md §1)", () => {
  it("returns the segmented-abstract fixture for the requested pmid", async () => {
    const client = createTestQueryClient();
    const { result } = renderHook(() => useAbstract("38279812"), { wrapper: wrapperWithClient(client) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(FIXTURE_ABSTRACT_RESPONSE);
    expect(result.current.data?.segments[0].kind).toBe("section_header");
  });

  it("stays disabled (no fetch) when pmid is undefined — one-ahead prefetch gating (§5.6)", () => {
    const client = createTestQueryClient();
    const { result } = renderHook(() => useAbstract(undefined), { wrapper: wrapperWithClient(client) });

    expect(result.current.fetchStatus).toBe("idle");
    expect(result.current.data).toBeUndefined();
  });

  it("respects the enabled option for deferring the next-up fetch", () => {
    const client = createTestQueryClient();
    const { result } = renderHook(() => useAbstract("38279812", { enabled: false }), {
      wrapper: wrapperWithClient(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
  });
});
