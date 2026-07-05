import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import { queryKeys } from "./queryKeys";
import { ApiError, type DecisionUpdateRequest, type QueueResponse } from "./types";
import { PermanentRetryFailure, useRetryQueueStore } from "../state/retryQueueStore";

interface UpdateDecisionVariables extends DecisionUpdateRequest {
  pmid: string;
}

function performDecision(variables: UpdateDecisionVariables): Promise<void> {
  const { pmid, decision, decided_via } = variables;
  return apiFetch<void>(`/decisions/${pmid}`, { method: "PATCH", body: { decision, decided_via } });
}

/** Adversarial-review fix (Finding 1, "TASK 4C SEC15.6 FOLLOW-UP
 * REVIEW"): the *queued* retry attempt (via `retryQueueStore`) can fail
 * for a genuinely different reason than the original network drop that
 * queued it in the first place — the session may have expired, the
 * paper may have been removed server-side, etc. by the time reconnect
 * actually replays it. A real `ApiError` here means retrying the exact
 * same request again won't help, so it's translated into
 * `PermanentRetryFailure` — `retryQueueStore`'s own generic signal to
 * stop retrying and surface this as a real failure — rather than being
 * left to loop forever the way an undifferentiated catch would. Any
 * other rejection (another network-level failure) is left to propagate
 * as-is, so the item stays queued for the *next* reconnect exactly as
 * before. */
function retryDecision(variables: UpdateDecisionVariables, queryClient: QueryClient): () => Promise<void> {
  return () =>
    performDecision(variables)
      .then(() => invalidateQueueAndSaved(queryClient))
      .catch((retryError: unknown) => {
        if (retryError instanceof ApiError) {
          throw new PermanentRetryFailure(
            retryError.message || `Couldn't save the decision for paper ${variables.pmid}.`,
          );
        }
        throw retryError;
      });
}

function invalidateQueueAndSaved(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: queryKeys.queue });
  void queryClient.invalidateQueries({ queryKey: queryKeys.saved });
}

/** `PATCH /api/v1/decisions/{pmid}` (§10.4) — the single decision
 * function every input method (swipe, tap, keyboard, auto-decide) calls
 * through (§11.4). Per §11.2, this optimistically updates the queue
 * cache immediately so the swipe animation (§5.3b) never waits on a
 * network round-trip, then reconciles with the server response.
 *
 * Two distinct failure modes, per §4.5 vs. an ordinary server-side
 * rejection:
 *  - A real `ApiError` (the request reached the server; it said no —
 *    `not_found`, `validation_error`, etc.) rolls the optimistic update
 *    back, since the decision genuinely didn't take.
 *  - A network-level failure (`fetch` itself rejected — no `ApiError`
 *    was ever constructed because no response came back at all, the
 *    §4.5 "offline mid-session" case) does *not* roll back: the user's
 *    decision is kept locally and handed to `retryQueueStore` so
 *    `offlineSync`'s real `online` listener (Task 4C) replays it
 *    automatically on reconnect (§4.5 point 4) — this is the "queued
 *    actions ... retried on reconnect" mechanism BuildPlan.md's Task 4C
 *    scoped but that, until this pass, had no real producer wiring it
 *    up (see this task's build-log START entry). */
export function useUpdateDecision() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: performDecision,

    onMutate: async ({ pmid, decision }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.queue });
      const previousQueue = queryClient.getQueryData<QueueResponse>(queryKeys.queue);

      if (previousQueue) {
        queryClient.setQueryData<QueueResponse>(queryKeys.queue, {
          ...previousQueue,
          items: previousQueue.items.map((item) =>
            item.pmid === pmid ? { ...item, decision } : item,
          ),
        });
      }

      return { previousQueue };
    },

    onError: (err, vars, context) => {
      if (!(err instanceof ApiError)) {
        useRetryQueueStore.getState().enqueue({
          id: `decision-${vars.pmid}`,
          label: `Save decision for paper ${vars.pmid}`,
          run: retryDecision(vars, queryClient),
        });
        return;
      }

      if (context?.previousQueue) {
        queryClient.setQueryData(queryKeys.queue, context.previousQueue);
      }
    },

    onSettled: (_data, error) => {
      // A network-level failure was just handed to `retryQueueStore`
      // above instead of rolled back — invalidating now would trigger an
      // immediate refetch that (still offline) just fails again and
      // risks thrashing the optimistic cache before reconnect actually
      // happens. The queued `run()` invalidates on its own once it
      // eventually succeeds.
      if (error && !(error instanceof ApiError)) return;
      invalidateQueueAndSaved(queryClient);
    },
  });
}
