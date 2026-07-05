import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

/** A fresh, retry-disabled QueryClient per test so failures resolve
 * immediately instead of TanStack Query's default backoff delaying
 * assertions. `mutations.networkMode: "always"` matches the real
 * `api/queryClient.ts` (see its own comment) — without it, a test that
 * also flips `navigator`/`window` online state (none currently do, but
 * a future one might) would silently pause mutations here too, unlike
 * production. */
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false, networkMode: "always" },
    },
  });
}

export function wrapperWithClient(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}
