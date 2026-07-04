import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import { queryKeys } from "./queryKeys";
import type { SegmentedAbstractResponse } from "./types";

/** `GET /api/v1/papers/{pmid}/abstract` (§10.4, CONTRACTS.md §1) — called
 * only for the current and next-up paper (§5.6's one-ahead rule).
 * `enabled` lets a caller defer fetching the next-up paper's abstract
 * until playback of the current one actually starts, per §11.3's note
 * that the playback engine consumes already-cached data rather than
 * fetching it itself. */
export function useAbstract(pmid: string | undefined, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.abstract(pmid ?? ""),
    queryFn: () => apiFetch<SegmentedAbstractResponse>(`/papers/${pmid}/abstract`),
    enabled: Boolean(pmid) && (options.enabled ?? true),
    staleTime: Infinity, // Paper abstracts are immutable once fetched (§9.2 cache).
  });
}
