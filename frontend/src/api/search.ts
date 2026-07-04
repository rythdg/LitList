import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import { queryKeys } from "./queryKeys";
import type { QueueResponse, SearchRequest, SearchSettingsResponse } from "./types";

/** `POST /api/v1/search` (§10.4) — replaces the session's current
 * `SearchSession` (§3.5/§9.2) and returns the fresh queue. On success we
 * seed the queue query cache directly rather than refetching, since the
 * response already *is* the queue. */
export function useRunSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: SearchRequest) => apiFetch<QueueResponse>("/search", { method: "POST", body }),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.queue, data);
    },
  });
}

/** `GET /api/v1/search/settings` (§10.4) — pre-fill for Screen B (§3.5). */
export function useSearchSettings() {
  return useQuery({
    queryKey: queryKeys.searchSettings,
    queryFn: () => apiFetch<SearchSettingsResponse>("/search/settings"),
  });
}
