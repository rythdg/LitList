import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { apiFetch, API_BASE_URL } from "./client";
import { server } from "./mocks/server";
import { ApiError } from "./types";

describe("apiFetch (§10.3/CONTRACTS.md §2)", () => {
  it("returns parsed JSON on a 2xx response", async () => {
    server.use(
      http.get(`${API_BASE_URL}/ping`, () => HttpResponse.json({ ok: true })),
    );
    const result = await apiFetch<{ ok: boolean }>("/ping");
    expect(result).toEqual({ ok: true });
  });

  it("throws an ApiError carrying code+message from the pinned error shape on non-2xx", async () => {
    server.use(
      http.get(`${API_BASE_URL}/boom`, () =>
        HttpResponse.json(
          { error: { code: "service_unavailable", message: "PubMed is currently unavailable." } },
          { status: 503 },
        ),
      ),
    );

    await expect(apiFetch("/boom")).rejects.toMatchObject({
      code: "service_unavailable",
      message: "PubMed is currently unavailable.",
      status: 503,
    });
  });

  it("falls back to a safe internal_error when the error body isn't the pinned shape", async () => {
    server.use(http.get(`${API_BASE_URL}/broken`, () => new HttpResponse("<html>502</html>", { status: 502 })));

    let thrown: unknown;
    try {
      await apiFetch("/broken");
    } catch (err) {
      thrown = err;
    }

    expect(thrown).toBeInstanceOf(ApiError);
    expect((thrown as ApiError).code).toBe("internal_error");
    // Never surfaces raw response text (§10.3's "never leak internals").
    expect((thrown as ApiError).message).not.toContain("<html>");
  });

  it("sends credentials so the session cookie (§10.2) is included", async () => {
    let receivedCredentials: RequestCredentials | undefined;
    const originalFetch = globalThis.fetch;
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
      receivedCredentials = init?.credentials;
      return originalFetch(input, init);
    }) as typeof fetch;

    server.use(http.get(`${API_BASE_URL}/whoami`, () => HttpResponse.json({})));
    await apiFetch("/whoami");
    globalThis.fetch = originalFetch;

    expect(receivedCredentials).toBe("include");
  });
});
