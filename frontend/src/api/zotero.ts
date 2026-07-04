import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, API_BASE_URL } from "./client";
import { queryKeys } from "./queryKeys";
import type {
  CreateZoteroCollectionRequest,
  CreateZoteroCollectionResponse,
  ZoteroCollectionsResponse,
  ZoteroPushRequest,
  ZoteroPushResponse,
} from "./types";

/** `GET /api/v1/zotero/collections` (§10.4, §8.4). A `zotero_not_connected`
 * `ApiError` (CONTRACTS.md §2) is how the frontend learns to show the
 * "Connect to Zotero" step (§5.5) — callers should check `error.code`
 * on a thrown `ApiError`, not treat every failure the same. */
export function useZoteroCollections(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.zoteroCollections,
    queryFn: () => apiFetch<ZoteroCollectionsResponse>("/zotero/collections"),
    enabled: options.enabled ?? true,
  });
}

/** `POST /api/v1/zotero/collections` (§10.4, §8.5) — the "+ New
 * collection" inline field on Screen D1 (§5.5). */
export function useCreateZoteroCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: CreateZoteroCollectionRequest) =>
      apiFetch<CreateZoteroCollectionResponse>("/zotero/collections", { method: "POST", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.zoteroCollections });
    },
  });
}

/** `POST /api/v1/zotero/push` (§10.4, §8.6/§8.7, CONTRACTS.md §3). Always
 * a per-PMID result list — callers must inspect `results[].status` per
 * item rather than treating a 200 as "everything saved" (§5.5 Step 3b's
 * partial-failure copy). */
export function useZoteroPush() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: ZoteroPushRequest) =>
      apiFetch<ZoteroPushResponse>("/zotero/push", { method: "POST", body }),
    onSettled: () => {
      // A successful push doesn't change queue/saved decisions, but it's
      // cheap to make sure any server-side export bookkeeping (§9.2
      // ZoteroExport rows) that other views read is fresh.
      void queryClient.invalidateQueries({ queryKey: queryKeys.saved });
    },
  });
}

/** §9.6's "Disconnect Zotero" action (Saved List Panel, §5.4) — deletes
 * the local `ZoteroConnection` row immediately. No dedicated endpoint is
 * pinned in CONTRACTS.md/§10.4 yet; this hook targets the natural
 * REST-ful counterpart to `GET /zotero/collections` pending that being
 * added to §10.4 — flagging here rather than inventing an unrelated shape. */
export function useDisconnectZotero() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => apiFetch<void>("/zotero/connection", { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.zoteroCollections });
    },
  });
}

/** `GET /api/v1/export.csv` (§10.4, §8.8) streams a file — there's no
 * JSON response to wrap in a query hook. Callers navigate the browser to
 * this URL (e.g. via an anchor's `href`) to trigger the native download,
 * consistent with it working even without a `ZoteroConnection`. */
export function getExportCsvUrl(): string {
  return `${API_BASE_URL}/export.csv`;
}
