import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE_URL } from "../../api/client";
import type { ZoteroPushResult } from "../../api/types";
import { useCreateZoteroCollection, useZoteroCollections, useZoteroPush } from "../../api/zotero";
import { getExportCsvUrl } from "../../api/zotero";
import { useNetworkStore } from "../../state/networkStore";
import { useZoteroPushFlowStore } from "../../state/zoteroPushFlowStore";
import type { ZoteroPushFlowProps, ZoteroPushStep } from "../../components/screens/ZoteroPushFlow";

export interface UseZoteroPushFlowControllerArgs {
  /** The PMIDs currently on the Saved List (§5.4) — this drives the
   *  whole flow's "what are we pushing" set; server-state, sourced from
   *  `useSaved()` by the caller (not refetched independently here). */
  pmids: string[];
  /** Called on Cancel/Done — the caller (e.g. `ZoteroPushModal.tsx`)
   *  owns whether "closed" means unmounting, hiding, or navigating. */
  onClose: () => void;
}

/**
 * Task 4B: drives `ZoteroPushFlow.tsx`'s full step machine (connect ->
 * choose_collection -> success/failure, §5.5) against the real
 * `GET/POST /zotero/collections` and `POST /zotero/push` endpoints
 * (§8.4-§8.7, CONTRACTS.md §3). `ZoteroPushFlow.tsx` itself stays purely
 * presentational (2B, untouched by this hook) — this is the "which step,
 * with what data" decision layer §11.2 puts in the TanStack-Query-backed
 * half of the app, not inside the component.
 *
 * **Partial-failure handling (§8.6/§8.7, CONTRACTS.md §3):** a push
 * response is always a per-PMID result list, never all-or-nothing. This
 * hook inspects `results[].status` itself rather than trusting the
 * mutation's mere HTTP success/failure — a 200 response with some
 * per-item failures routes to the `"failure"` step (reason `"push"`),
 * and a subsequent Retry only resubmits the PMIDs that actually failed
 * (tracked in `lastResults`), never the whole list again. A `"connection"`
 * failure (the mutation itself erroring — e.g. the connection was
 * revoked mid-flow) is kept distinct from a `"push"` failure (the
 * mutation succeeded but individual items didn't) per `ZoteroPushFlow`'s
 * existing `failureReason` prop, which this hook drives rather than
 * reinvents.
 */
export function useZoteroPushFlowController({
  pmids,
  onClose,
}: UseZoteroPushFlowControllerArgs): ZoteroPushFlowProps {
  const collections = useZoteroCollections();
  const createCollection = useCreateZoteroCollection();
  const push = useZoteroPush();
  const isOnline = useNetworkStore((state) => state.isOnline);
  const setPushPending = useZoteroPushFlowStore((state) => state.setPushPending);

  const [selectedCollectionKey, setSelectedCollectionKey] = useState<string | null>(null);
  const [lastResults, setLastResults] = useState<ZoteroPushResult[] | null>(null);
  const [connectionFailed, setConnectionFailed] = useState(false);

  // Post-review fix (finding #1, adversarial-generalist "TASK 4B
  // REVIEW"): `push.isPending` is React state — two synchronous calls to
  // `runPush` in the same tick (a fast double-click, or Save immediately
  // followed by Retry) both close over the *same*, not-yet-committed
  // `isPending` value and both pass an `if (push.isPending) return`
  // guard built on it, exactly the re-entrancy failure mode Task 2D's
  // playback engine hit and fixed with a plain ref (see that module's
  // own "TASK 2D — PIVOT" build-log entry). `isPushingRef` is this
  // hook's equivalent: a synchronous source of truth, set `true`
  // immediately before calling `mutate` and cleared in `onSettled`
  // (success *and* error), never read from React state.
  const isPushingRef = useRef(false);

  // Post-review fix (adversarial-generalist "TASK 4B REVIEW", finding
  // #2): mirror `push.isPending` into the shared store so surfaces that
  // don't render this flow at all — the Saved List panel's "Disconnect
  // Zotero" button — can still guard against racing an in-flight push.
  // Reset to `false` on unmount too, so a stale `true` never lingers
  // after this flow's modal closes mid-request.
  useEffect(() => {
    setPushPending(push.isPending);
  }, [push.isPending, setPushPending]);
  useEffect(() => () => setPushPending(false), [setPushPending]);

  // §10.4's note on `/zotero/collections`: a `zotero_not_connected` error
  // (not yet loaded, or genuinely never connected) both read as "not
  // connected" here — `ZoteroPushFlow`'s own "connect" step covers both,
  // there is no separate "checking..." step in its design (§5.5).
  const isConnected = collections.data?.connected === true;

  const failedPmids = useMemo(() => {
    if (!lastResults) return null;
    const failed = new Set(lastResults.filter((r) => r.status === "failure").map((r) => r.pmid));
    return pmids.filter((pmid) => failed.has(pmid));
  }, [lastResults, pmids]);

  const runPush = useCallback(
    (targetPmids: string[]) => {
      // Post-review fix (finding #1): a rapid double-click/double-call
      // (Save then Save again, or Save then Retry before the first
      // request resolves) must never fire two concurrent pushes for the
      // same PMIDs — the backend has no idempotency key, so that would
      // create genuine duplicate items in the user's real Zotero
      // library. `ZoteroPushFlow.tsx`'s Save/Retry buttons are also
      // disabled while `isSaving` (below), but `isPushingRef` (a
      // synchronous ref, not React state — see its own docstring) is
      // the guard that actually holds even if a caller bypasses the UI.
      if (isPushingRef.current) {
        return;
      }
      if (!selectedCollectionKey || selectedCollectionKey === "__new__" || targetPmids.length === 0) {
        return;
      }
      isPushingRef.current = true;
      setConnectionFailed(false);
      push.mutate(
        { collection_key: selectedCollectionKey, pmids: targetPmids },
        {
          onSuccess: (response) => setLastResults(response.results),
          onError: () => setConnectionFailed(true),
          onSettled: () => {
            isPushingRef.current = false;
          },
        },
      );
    },
    [push, selectedCollectionKey],
  );

  const handleSave = useCallback(() => {
    setLastResults(null);
    runPush(pmids);
  }, [runPush, pmids]);

  const handleRetry = useCallback(() => {
    if (connectionFailed || !isConnected) {
      // A connection-level failure (or the connection having lapsed) —
      // re-check connection status rather than blindly resubmitting.
      void collections.refetch();
      setConnectionFailed(false);
      return;
    }
    // Partial-push retry (§8.7): only the PMIDs that actually failed.
    runPush(failedPmids && failedPmids.length > 0 ? failedPmids : pmids);
  }, [connectionFailed, isConnected, collections, runPush, failedPmids, pmids]);

  const handleCreateCollection = useCallback(
    (name: string) => {
      const trimmed = name.trim();
      if (!trimmed) return;
      createCollection.mutate(
        { name: trimmed },
        { onSuccess: (response) => setSelectedCollectionKey(response.collection.key) },
      );
    },
    [createCollection],
  );

  const handleConnect = useCallback(() => {
    // A real, full browser navigation — this is not a `fetch`, it's the
    // start of the OAuth 1.0a handshake (§8.2 step 2), which must bounce
    // the whole page to Zotero's own site and back. Never call this via
    // `apiFetch`/XHR (§10.5's "external calls are server-side only" is
    // about *this backend* calling Zotero directly; the browser
    // navigating to our own backend's redirecting route is how §8.2's
    // flow starts).
    window.location.href = `${API_BASE_URL}/zotero/auth/start`;
  }, []);

  const handleDownloadCsv = useCallback(() => {
    window.location.href = getExportCsvUrl();
  }, []);

  // Post-review fix (finding #2): Cancel must not dismiss the modal
  // while a push is actually in flight — the backend completes an
  // already-started push independent of the modal closing, so silently
  // allowing Cancel here would let the user believe they'd backed out
  // while a write to their real Zotero library was still landing. The
  // button itself is also disabled (`isSaving`, in `ZoteroPushFlow.tsx`)
  // — this guard is the one that holds regardless of how `onCancel` gets
  // invoked.
  const handleCancel = useCallback(() => {
    if (isPushingRef.current) {
      return;
    }
    onClose();
  }, [onClose]);

  const hasFailure =
    connectionFailed || (lastResults?.some((result) => result.status === "failure") ?? false);
  const hasSucceeded =
    !connectionFailed && Boolean(lastResults) && lastResults!.every((result) => result.status === "success");

  let step: ZoteroPushStep;
  if (!isConnected) {
    step = "connect";
  } else if (hasSucceeded) {
    step = "success";
  } else if (hasFailure) {
    step = "failure";
  } else {
    step = "choose_collection";
  }

  return {
    step,
    paperCount: pmids.length,
    collections: collections.data?.collections ?? [],
    selectedCollectionKey,
    onSelectCollection: setSelectedCollectionKey,
    onCreateCollection: handleCreateCollection,
    onConnect: handleConnect,
    onCancel: handleCancel,
    onSave: handleSave,
    onRetry: handleRetry,
    onDownloadCsv: handleDownloadCsv,
    onDone: onClose,
    isOffline: !isOnline,
    failureReason: connectionFailed ? "connection" : "push",
    // Post-review fix (finding #1): drives `ZoteroPushFlow.tsx`'s
    // Save/Retry buttons disabled+relabeled while a push is actually in
    // flight, on top of `runPush`'s own early-return guard above.
    isSaving: push.isPending,
  };
}
