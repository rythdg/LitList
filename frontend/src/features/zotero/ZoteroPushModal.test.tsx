import { act, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { API_BASE_URL } from "../../api/client";
import { FIXTURE_SAVED_RESPONSE } from "../../api/mocks/fixtures";
import { server } from "../../api/mocks/server";
import { createTestQueryClient, wrapperWithClient } from "../../api/testUtils";
import { useZoteroPushFlowStore } from "../../state/zoteroPushFlowStore";
import { ZoteroPushModal } from "./ZoteroPushModal";

describe("ZoteroPushModal (Task 4B drop-in for App.tsx's Saved List panel)", () => {
  afterEach(() => {
    useZoteroPushFlowStore.setState({ isOpen: false });
  });

  it("renders nothing when the push flow isn't open", () => {
    const client = createTestQueryClient();
    render(<ZoteroPushModal />, { wrapper: wrapperWithClient(client) });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders the real push flow (sourced from useSaved's PMIDs) once opened, and Cancel closes it again", async () => {
    server.use(
      http.get(`${API_BASE_URL}/saved`, () => HttpResponse.json(FIXTURE_SAVED_RESPONSE)),
    );
    act(() => useZoteroPushFlowStore.getState().open());

    const client = createTestQueryClient();
    render(<ZoteroPushModal />, { wrapper: wrapperWithClient(client) });

    expect(screen.getByRole("dialog", { name: /save to zotero/i })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByTestId("zotero-step-choose-collection")).toBeInTheDocument(),
    );
    expect(screen.getByText(`Save ${FIXTURE_SAVED_RESPONSE.items.length} papers to:`)).toBeInTheDocument();

    act(() => screen.getByRole("button", { name: /cancel/i }).click());
    expect(useZoteroPushFlowStore.getState().isOpen).toBe(false);
  });
});
