import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useQueue } from "./queue";
import { FIXTURE_QUEUE_RESPONSE } from "./mocks/fixtures";
import { createTestQueryClient, wrapperWithClient } from "./testUtils";

describe("useQueue (§10.4 GET /queue)", () => {
  it("returns the MSW-mocked queue fixture", async () => {
    const client = createTestQueryClient();
    const { result } = renderHook(() => useQueue(), { wrapper: wrapperWithClient(client) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(FIXTURE_QUEUE_RESPONSE);
  });
});
