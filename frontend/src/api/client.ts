import { ApiError, type ApiErrorResponse } from "./types";

/**
 * Base URL for LitList's own API. Configurable via Vite env so the
 * frontend and backend can be deployed on different origins (SPEC.md
 * §10.7) without a code change.
 */
export const API_BASE_URL: string =
  (import.meta.env?.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
}

/**
 * The one fetch wrapper every hook in api/ goes through. Per SPEC.md
 * §10.2/§10.7 the session cookie is the *only* credential the frontend
 * ever holds, sent automatically via `credentials: "include"` — no
 * token/secret is ever attached in JS. Every non-2xx response is parsed
 * against CONTRACTS.md §2's pinned `{"error": {code, message}}` shape and
 * re-thrown as an `ApiError` so every caller has exactly one error
 * shape to branch on.
 */
export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, signal } = options;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    credentials: "include",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  if (!response.ok) {
    let parsed: ApiErrorResponse | null;
    try {
      parsed = (await response.json()) as ApiErrorResponse;
    } catch {
      // Response body wasn't JSON (e.g. a proxy-level 502) — fall back to
      // a generic, safe message rather than surfacing raw response text.
      parsed = null;
    }

    if (parsed?.error) {
      throw new ApiError(response.status, parsed.error);
    }

    throw new ApiError(response.status, {
      code: "internal_error",
      message: "Something went wrong. Please try again shortly.",
    });
  }

  // 204 No Content (e.g. DELETE) has no body to parse.
  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
