import { renderHook, waitFor, act } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { API_BASE_URL } from "./client";
import { useZoteroCollections, useZoteroPush, getExportCsvUrl } from "./zotero";
import {
  FIXTURE_ZOTERO_COLLECTIONS_RESPONSE,
  FIXTURE_ZOTERO_NOT_CONNECTED_ERROR,
  FIXTURE_ZOTERO_PUSH_RESPONSE,
} from "./mocks/fixtures";
import { server } from "./mocks/server";
import { createTestQueryClient, wrapperWithClient } from "./testUtils";
import { ApiError } from "./types";

describe("Zotero hooks (§10.4, §8.4-§8.7, CONTRACTS.md §3)", () => {
  it("returns the collections fixture", async () => {
    const client = createTestQueryClient();
    const { result } = renderHook(() => useZoteroCollections(), { wrapper: wrapperWithClient(client) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(FIXTURE_ZOTERO_COLLECTIONS_RESPONSE);
  });

  it("surfaces zotero_not_connected as an ApiError code, not a generic failure", async () => {
    server.use(
      http.get(`${API_BASE_URL}/zotero/collections`, () =>
        HttpResponse.json(FIXTURE_ZOTERO_NOT_CONNECTED_ERROR, { status: 401 }),
      ),
    );

    const client = createTestQueryClient();
    const { result } = renderHook(() => useZoteroCollections(), { wrapper: wrapperWithClient(client) });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect((result.current.error as ApiError).code).toBe("zotero_not_connected");
  });

  it("returns a per-PMID push result list, never all-or-nothing (§8.7)", async () => {
    const client = createTestQueryClient();
    const { result } = renderHook(() => useZoteroPush(), { wrapper: wrapperWithClient(client) });

    let response: typeof FIXTURE_ZOTERO_PUSH_RESPONSE | undefined;
    await act(async () => {
      response = await result.current.mutateAsync({
        collection_key: "ABCD1234",
        pmids: ["38279812", "38279813"],
      });
    });

    expect(response).toEqual(FIXTURE_ZOTERO_PUSH_RESPONSE);
    expect(response?.results.filter((r) => r.status === "success")).toHaveLength(1);
    expect(response?.results.filter((r) => r.status === "failure")).toHaveLength(1);
  });

  it("builds the export.csv URL against the configured API base (§8.8, no Zotero dependency)", () => {
    expect(getExportCsvUrl()).toBe(`${API_BASE_URL}/export.csv`);
  });
});
