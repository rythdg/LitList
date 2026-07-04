import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import { queryKeys } from "./queryKeys";
import type { SavedResponse } from "./types";

/** `GET /api/v1/saved` (§10.4, §5.4). */
export function useSaved() {
  return useQuery({
    queryKey: queryKeys.saved,
    queryFn: () => apiFetch<SavedResponse>("/saved"),
  });
}

/** `DELETE /api/v1/saved/{pmid}` (§10.4, §4.7) — sets the decision back
 * to `not_interested` server-side rather than deleting the row; this
 * does not resurrect the card in the live queue, so only the saved-list
 * cache needs reconciling here. */
export function useRemoveSaved() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (pmid: string) => apiFetch<void>(`/saved/${pmid}`, { method: "DELETE" }),

    onMutate: async (pmid) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.saved });
      const previousSaved = queryClient.getQueryData<SavedResponse>(queryKeys.saved);

      if (previousSaved) {
        queryClient.setQueryData<SavedResponse>(queryKeys.saved, {
          items: previousSaved.items.filter((item) => item.paper.pmid !== pmid),
        });
      }

      return { previousSaved };
    },

    onError: (_err, _pmid, context) => {
      if (context?.previousSaved) {
        queryClient.setQueryData(queryKeys.saved, context.previousSaved);
      }
    },

    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.saved });
    },
  });
}
