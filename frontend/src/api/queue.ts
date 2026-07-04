import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import { queryKeys } from "./queryKeys";
import type { QueueResponse } from "./types";

/** `GET /api/v1/queue` (§10.4) — the current `SearchSession`'s queue.
 * The backend transparently pages in more results as the queue runs low
 * (§7.9); the frontend never has to ask for "more" explicitly, so this
 * is a plain query, not an infinite query. */
export function useQueue() {
  return useQuery({
    queryKey: queryKeys.queue,
    queryFn: () => apiFetch<QueueResponse>("/queue"),
  });
}
