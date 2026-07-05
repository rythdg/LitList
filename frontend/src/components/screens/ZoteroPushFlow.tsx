import { ErrorState } from "../ErrorState";

/**
 * Screen D1 — Zotero push sub-flow (SPEC.md §5.5).
 *
 * Four steps plus the offline "pending" variant of Step 2, driven by a
 * `step` prop the parent controls (server-state transitions belong to
 * TanStack Query per §11.2 — this component only renders whichever step
 * it's told to). Step 3b is this task's cited "error" screen-state —
 * rendered via the shared `ErrorState` component (Task 4C, §11.7) so its
 * copy stays in sync with every other error surface in the app; this
 * component still owns the `failureReason` prop (connection vs. push)
 * since that distinction is specific to this flow (§4.4/§5.5).
 */
export interface ZoteroCollection {
  key: string;
  name: string;
}

export type ZoteroPushStep =
  | "connect"
  | "choose_collection"
  | "success"
  | "failure";

export interface ZoteroPushFlowProps {
  step: ZoteroPushStep;
  paperCount: number;
  collections: ZoteroCollection[];
  selectedCollectionKey: string | null;
  onSelectCollection: (key: string) => void;
  onCreateCollection: (name: string) => void;
  onConnect: () => void;
  onCancel: () => void;
  onSave: () => void;
  onRetry: () => void;
  onDownloadCsv: () => void;
  onDone: () => void;
  /** §5.5's offline behavior: "Save" becomes "Pending — will retry when
   *  back online" plus a manual retry-now affordance, per §5's top
   *  resolution note. */
  isOffline?: boolean;
  /** Distinguishes connection failure from push failure copy (§5.5's two
   *  distinct message variants sharing the Step 3b layout). */
  failureReason?: "connection" | "push";
  /** Task 4B post-review fix: true while a push request is actually in
   *  flight (`useZoteroPush().isPending`). Disables Save/Cancel (choose_
   *  collection step) and Retry (failure step) so a rapid double-click
   *  can never fire two concurrent `POST /zotero/push` requests for the
   *  same PMIDs (the backend has no idempotency key — a duplicate
   *  request means duplicate items in the user's real Zotero library),
   *  and so Cancel can't dismiss the modal while a write that already
   *  started is still landing. */
  isSaving?: boolean;
}

export function ZoteroPushFlow({
  step,
  paperCount,
  collections,
  selectedCollectionKey,
  onSelectCollection,
  onCreateCollection,
  onConnect,
  onCancel,
  onSave,
  onRetry,
  onDownloadCsv,
  onDone,
  isOffline = false,
  failureReason = "push",
  isSaving = false,
}: ZoteroPushFlowProps) {
  if (step === "connect") {
    return (
      <div className="flex flex-col gap-3 p-4 text-slate-900" data-testid="zotero-step-connect">
        <p>Connect your Zotero account to save papers.</p>
        <button
          type="button"
          onClick={onConnect}
          className="rounded bg-slate-900 px-4 py-2 font-medium text-white"
        >
          Connect to Zotero
        </button>
      </div>
    );
  }

  if (step === "choose_collection") {
    return (
      <div className="flex flex-col gap-3 p-4 text-slate-900" data-testid="zotero-step-choose-collection">
        <p>Save {paperCount} papers to:</p>
        <fieldset>
          {collections.map((collection) => (
            <label key={collection.key} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="zotero-collection"
                checked={selectedCollectionKey === collection.key}
                onChange={() => onSelectCollection(collection.key)}
              />
              {collection.name}
            </label>
          ))}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="zotero-collection"
              checked={selectedCollectionKey === "__new__"}
              onChange={() => onSelectCollection("__new__")}
            />
            + New collection...
          </label>
        </fieldset>
        {selectedCollectionKey === "__new__" ? (
          <input
            type="text"
            placeholder="Collection name"
            aria-label="New collection name"
            onBlur={(event) => onCreateCollection(event.target.value)}
            className="rounded border border-slate-300 px-2 py-1"
          />
        ) : null}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSaving}
            className="rounded border border-slate-300 px-4 py-2 disabled:cursor-not-allowed disabled:text-slate-400"
          >
            Cancel
          </button>
          {isOffline ? (
            <button
              type="button"
              onClick={onRetry}
              disabled={isSaving}
              data-testid="zotero-pending-retry"
              className="rounded bg-slate-300 px-4 py-2 text-slate-700 disabled:cursor-not-allowed"
            >
              Pending — will retry when back online (Retry now)
            </button>
          ) : (
            <button
              type="button"
              onClick={onSave}
              disabled={isSaving}
              className="rounded bg-slate-900 px-4 py-2 font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {isSaving ? "Saving…" : "Save"}
            </button>
          )}
        </div>
      </div>
    );
  }

  if (step === "success") {
    return (
      <div className="flex flex-col gap-3 p-4 text-slate-900" data-testid="zotero-step-success">
        <p role="status">
          ✓ Saved {paperCount} papers to the selected collection.
        </p>
        <button type="button" onClick={onDone} className="rounded bg-slate-900 px-4 py-2 font-medium text-white">
          Done
        </button>
      </div>
    );
  }

  // step === "failure" — this task's cited "error" screen state (§5.5 3b),
  // rendered through the shared ErrorState component (Task 4C) so the
  // connection-vs-push distinction and the CSV-fallback affordance stay
  // consistent with every other error surface in the app.
  return (
    <div data-testid="zotero-step-failure">
      <ErrorState
        context="zotero_push"
        error={{
          code: failureReason === "connection" ? "zotero_not_connected" : "internal_error",
          message:
            failureReason === "connection"
              ? "Couldn't verify your Zotero login."
              : "The push to Zotero didn't go through.",
        }}
        onRetry={onRetry}
        retryDisabled={isSaving}
        onDownloadCsv={onDownloadCsv}
      />
    </div>
  );
}
