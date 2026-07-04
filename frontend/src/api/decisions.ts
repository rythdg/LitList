import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import { queryKeys } from "./queryKeys";
import type { DecisionUpdateRequest, QueueResponse } from "./types";

interface UpdateDecisionVariables extends DecisionUpdateRequest {
  pmid: string;
}

/** `PATCH /api/v1/decisions/{pmid}` (§10.4) — the single decision
 * function every input method (swipe, tap, keyboard, auto-decide) calls
 * through (§11.4). Per §11.2, this optimistically updates the queue
 * cache immediately so the swipe animation (§5.3b) never waits on a
 * network round-trip, then reconciles with the server response — and
 * rolls the optimistic update back if the request actually fails. */
export function useUpdateDecision() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ pmid, decision, decided_via }: UpdateDecisionVariables) =>
      apiFetch<void>(`/decisions/${pmid}`, { method: "PATCH", body: { decision, decided_via } }),

    onMutate: async ({ pmid, decision }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.queue });
      const previousQueue = queryClient.getQueryData<QueueResponse>(queryKeys.queue);

      if (previousQueue) {
        queryClient.setQueryData<QueueResponse>(queryKeys.queue, {
          ...previousQueue,
          items: previousQueue.items.map((item) =>
            item.paper.pmid === pmid ? { ...item, decision } : item,
          ),
        });
      }

      return { previousQueue };
    },

    onError: (_err, _vars, context) => {
      if (context?.previousQueue) {
        queryClient.setQueryData(queryKeys.queue, context.previousQueue);
      }
    },

    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.queue });
      void queryClient.invalidateQueries({ queryKey: queryKeys.saved });
    },
  });
}
