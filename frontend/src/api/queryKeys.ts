/**
 * Centralized TanStack Query keys, one array-shape per §10.4 endpoint
 * family, so invalidation (e.g. a decision PATCH invalidating the queue)
 * doesn't rely on hand-typed string keys scattered across hooks.
 */
export const queryKeys = {
  searchSettings: ["search-settings"] as const,
  queue: ["queue"] as const,
  abstract: (pmid: string) => ["abstract", pmid] as const,
  saved: ["saved"] as const,
  zoteroCollections: ["zotero-collections"] as const,
};
