/**
 * Integration test for Task 4C's most important distinction (§13.6 vs.
 * §4.5): a real `service_unavailable` response from the backend (mocked
 * here via MSW at the actual HTTP boundary `apiFetch` talks to, not a
 * hand-built ApiErrorBody) must render the *external-downtime* copy, and
 * must NOT flip `networkStore` into believing the browser itself is
 * offline — those are different conditions with different causes and
 * different user-facing advice.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { renderHook, act } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { API_BASE_URL } from "../api/client";
import { server } from "../api/mocks/server";
import { useRunSearch } from "../api/search";
import { createTestQueryClient, wrapperWithClient } from "../api/testUtils";
import type { ApiError } from "../api/types";
import { ErrorState } from "./ErrorState";
import { useNetworkStore } from "../state/networkStore";

const base = (path: string) => `${API_BASE_URL}${path}`;

describe("service_unavailable end-to-end through apiFetch -> ErrorState (§13.6, §4.5)", () => {
  afterEach(() => {
    useNetworkStore.setState({ isOnline: true });
  });

  it("renders the external-downtime message and leaves networkStore reporting online", async () => {
    server.use(
      http.post(base("/search"), () =>
        HttpResponse.json(
          { error: { code: "service_unavailable", message: "PubMed is currently unavailable. Please try again shortly." } },
          { status: 503 },
        ),
      ),
    );

    const client = createTestQueryClient();
    const { result } = renderHook(() => useRunSearch(), { wrapper: wrapperWithClient(client) });

    await act(async () => {
      await result.current
        .mutateAsync({
          query: "spiking neural networks",
          sort: "relevance",
          read_aloud_fields: [],
          default_swipe_behavior: "not_interested",
          speed: 1,
        })
        .catch(() => {
          // Expected — asserted via result.current.error below.
        });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    const apiError = result.current.error as ApiError;
    expect(apiError.code).toBe("service_unavailable");

    render(<ErrorState error={apiError} isOffline={useNetworkStore.getState().isOnline === false} />);

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/currently unavailable/i);
    expect(alert).not.toHaveTextContent(/you're offline/i);

    // The whole point of a distinct backend code: the browser's own
    // connectivity is untouched by this failure.
    expect(useNetworkStore.getState().isOnline).toBe(true);
  });
});
