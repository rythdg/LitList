/**
 * App-level wiring (BuildPlan.md Task 4A, SPEC.md §3.3/§5/§11.2-§11.4).
 *
 * This is the first real composition of Screen A-D against actual
 * TanStack Query hooks (`api/`) and Zustand stores (`state/`) — Tier 0
 * left `App.tsx` as a scaffolding placeholder; Tier 2 built each screen
 * presentationally against fixtures. This file is deliberately the
 * *only* place that:
 *  - decides which panel (`search` | `stack` | `saved`) is visible,
 *    driven by `panelStore` (§11.2's UI-only state);
 *  - assembles `usePlaybackEngine`'s `PlaybackItem[]` queue from the real
 *    queue item (title/metadata, not yet pinned by CONTRACTS.md) plus
 *    the real `GET /papers/{pmid}/abstract` response (CONTRACTS.md §1);
 *  - owns the single decision function (§11.4): every input path (swipe,
 *    tap, keyboard, and the auto-decide-on-finish path, §5.3b) calls
 *    this exact same `decide()` closure, which triggers the optimistic
 *    queue update + `PATCH /decisions/{pmid}` (via `useUpdateDecision`)
 *    and prefetches the *next* next-up paper's abstract (§5.6 — only one
 *    card is ever pre-rendered ahead of the current one).
 *
 * Zotero collection selection/push (Screen D1, §5.5) is Task 4B's own
 * seam (2B's push UI <-> 3B's Zotero routes) — `<ZoteroPushModal />`
 * (`features/zotero/`) is 4B's self-contained drop-in for that, wired
 * below via `useZoteroPushFlowStore`'s open flag plus the real
 * `useDisconnectZotero`/`getExportCsvUrl` for the Saved List panel's own
 * Zotero-adjacent buttons (§5.4/§9.6) — this file only decides *when*
 * those fire, never how the push flow itself works internally.
 */
import { useCallback, useEffect, useMemo, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  apiFetch,
  ApiError,
  getExportCsvUrl,
  queryKeys,
  useAbstract,
  useDisconnectZotero,
  useQueue,
  useRemoveSaved,
  useRunSearch,
  useSaved,
  useSearchSettings,
  useUpdateDecision,
  useZoteroCollections,
  type DecidedVia,
  type DecisionValue,
  type QueueItem,
  type SegmentedAbstractResponse,
} from "./api";
import {
  usePanelStore,
  usePlaybackStore,
  useSearchDraftStore,
  useZoteroPushFlowStore,
  useNetworkStore,
} from "./state";
import { usePlaybackEngine } from "./playback/usePlaybackEngine";
import type { PlaybackItem } from "./playback/types";
import {
  EmptyQueueState,
  IdleScreen,
  SavedListPanel,
  SearchSettingsPanel,
  StackScreen,
  type DecisionSource,
} from "./components/screens";
import { CookieConsentNotice, ErrorState, PendingRetryBanner } from "./components";
import { confirmDisconnectDuringPush, ZoteroPushModal } from "./features/zotero";

/** Only `ApiError` instances carry CONTRACTS.md §2's `{code, message}`
 * shape `ErrorState` expects — a thrown network/parse error (no server
 * response reached at all) isn't one, and `isOffline` already covers
 * that case with its own copy (§4.5), so this just narrows/discards. */
function apiErrorOrNull(error: unknown): ApiError | null {
  return error instanceof ApiError ? error : null;
}

function metadataSpokenLine(item: QueueItem): string {
  return [item.last_author, item.journal, item.pub_date].filter(Boolean).join(", ");
}

function App() {
  const queryClient = useQueryClient();

  const activePanel = usePanelStore((state) => state.activePanel);
  const openSearch = usePanelStore((state) => state.openSearch);
  const openStack = usePanelStore((state) => state.openStack);
  const openSaved = usePanelStore((state) => state.openSaved);

  const draft = useSearchDraftStore();
  const playback = usePlaybackStore();

  const searchSettings = useSearchSettings();
  const runSearch = useRunSearch();
  const queue = useQueue();
  const saved = useSaved();
  const removeSaved = useRemoveSaved();
  const updateDecision = useUpdateDecision();
  const zoteroCollections = useZoteroCollections({ enabled: activePanel === "saved" });
  const disconnectZotero = useDisconnectZotero();
  const openZoteroPushFlow = useZoteroPushFlowStore((state) => state.open);
  const isZoteroPushPending = useZoteroPushFlowStore((state) => state.isPushPending);

  // Task 4B post-review fix: a push already in flight completes
  // independent of a concurrent disconnect (backend decrypts the token
  // once at request start) — require an explicit confirmation naming
  // that risk rather than silently disconnecting mid-push.
  const handleDisconnectZotero = useCallback(() => {
    if (confirmDisconnectDuringPush(isZoteroPushPending)) {
      disconnectZotero.mutate();
    }
  }, [isZoteroPushPending, disconnectZotero]);

  // §4.5/§13.6: the client-detected "am I online at all" fact (Task 4C's
  // `networkStore`, bridged from real browser events by `initOfflineSync`
  // in `main.tsx`) is distinct from — and takes priority over — any
  // individual query's `service_unavailable` error, per `errorCopy.ts`'s
  // own priority rule. Read once here so every screen below gets the
  // same answer rather than each re-deriving it.
  const isOffline = !useNetworkStore((state) => state.isOnline);

  // §3.5 pre-fill: hydrate the in-progress draft from the server's last
  // search settings exactly once when they first load. Later edits are
  // local-only (§11.2) until "Start" actually runs a new search.
  useEffect(() => {
    if (searchSettings.data) {
      draft.hydrate({
        query: searchSettings.data.query ?? "",
        sort: searchSettings.data.sort,
        readAloudFields: searchSettings.data.read_aloud_fields,
        defaultSwipeBehavior: searchSettings.data.default_swipe_behavior,
        speed: searchSettings.data.speed,
      });
    }
    // Only ever hydrate from the first successful load — re-running this
    // on every `searchSettings.data` identity change would clobber
    // in-progress edits made after that first load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchSettings.isSuccess]);

  // Screen A (Idle) vs. Screen C-empty (§5.1 vs §5.3a) hinges on whether
  // a search has ever run this visit — `GET /search/settings` returning
  // a non-null `query` means one ran in an earlier visit/reload;
  // `runSearch.isSuccess` covers one just run in this render session
  // before `searchSettings` would reflect it.
  const hasSearchedThisVisit = Boolean(searchSettings.data?.query) || runSearch.isSuccess;

  const pendingItems = useMemo(
    () => (queue.data?.items ?? []).filter((item) => item.decision === "pending"),
    [queue.data],
  );
  const currentItem = pendingItems[0] ?? null;
  const nextItem = pendingItems[1] ?? null;
  const afterNextItem = pendingItems[2] ?? null;

  const currentAbstract = useAbstract(currentItem?.pmid);
  // §5.6: only one card is ever pre-rendered ahead of the current one —
  // this pre-fetches the *next* card's abstract into the TanStack Query
  // cache while the current card plays, so advancing to it is instant.
  useAbstract(nextItem?.pmid, { enabled: Boolean(currentItem) });

  const items: PlaybackItem[] = useMemo(() => {
    if (!currentItem) return [];
    const list: PlaybackItem[] = [
      { key: "title", spokenText: currentItem.title, pauseClass: "structural" },
    ];
    const metadataLine = metadataSpokenLine(currentItem);
    if (metadataLine) {
      list.push({ key: "metadata", spokenText: metadataLine, pauseClass: "structural" });
    }
    for (const segment of currentAbstract.data?.segments ?? []) {
      list.push({
        key: `segment-${segment.index}`,
        spokenText: segment.spoken_text,
        pauseClass: segment.pause_class,
      });
    }
    return list;
  }, [currentItem, currentAbstract.data]);

  // `decide()` (defined below `engine` since it needs `engine.cancel`)
  // is called from *inside* `usePlaybackEngine`'s own `onFinished`
  // option, which has to be supplied before `decide` exists — bridged
  // via this ref (assigned in the effect right after `decide` is
  // (re)created) rather than reordering into a circular dependency.
  const decideRef = useRef<(pmid: string, decision: DecisionValue, decidedVia: DecidedVia) => void>(
    () => {},
  );

  const engine = usePlaybackEngine({
    items,
    speed: draft.speed,
    muted: playback.isMuted,
    onItemChange: (key) => {
      if (key && key.startsWith("segment-")) {
        playback.setHighlightedSegmentIndex(Number(key.slice("segment-".length)));
      } else {
        playback.setHighlightedSegmentIndex(null);
      }
    },
    onFinished: () => {
      // §5.3b: reaching the end of narration with no explicit
      // swipe/tap/keyboard decision auto-decides via the session's
      // configured default — routed through the exact same `decide()`
      // closure as every other input path, just with `decided_via:
      // "auto"` instead of `"swipe"`.
      if (currentItem) {
        decideRef.current(currentItem.pmid, draft.defaultSwipeBehavior, "auto");
      }
    },
  });

  // §11.4's single decision function. Swipe (gesture), tap, keyboard
  // (all via StackScreen's `onDecide` below) and the playback-finished
  // auto-decide path (via `decideRef` above) all call this exact
  // closure — never a divergent per-input-method implementation.
  //
  // BLOCKING fix (adversarial review, "TASK 4A REVIEW"): SPEC.md §6.6
  // requires `speechSynthesis.cancel()` synchronously as part of the
  // decision, "so there is no audible overlap between papers." This
  // previously only called `playback.resetForNewPaper()` (a Zustand
  // store write) — that flips the UI's `isPlaying`/highlight *display*
  // but never touched the engine's own live utterance, so the old
  // paper's narration kept speaking uninterrupted underneath. Now calls
  // `engine.cancel()` directly (the actual `speechSynthesis.cancel()` +
  // generation-bump + timer-invalidation, §11.3) instead of
  // `resetForNewPaper()` — `cancel()` already drives `isPlaying` back to
  // `false` (via the status-mirroring effect below) and the highlighted
  // segment back to `null` (via `onItemChange(null)`, which `cancel()`
  // triggers), so the store needs no separate write of its own here —
  // restoring the invariant that the engine, not the store, is the one
  // source of truth for playback state (§11.2/§11.3).
  const decide = useCallback(
    (pmid: string, decision: DecisionValue, decidedVia: DecidedVia) => {
      engine.cancel();
      updateDecision.mutate({ pmid, decision, decided_via: decidedVia });
      if (afterNextItem) {
        void queryClient.prefetchQuery({
          queryKey: queryKeys.abstract(afterNextItem.pmid),
          queryFn: () => apiFetch<SegmentedAbstractResponse>(`/papers/${afterNextItem.pmid}/abstract`),
          staleTime: Infinity,
        });
      }
    },
    [engine, updateDecision, afterNextItem, queryClient],
  );

  useEffect(() => {
    decideRef.current = decide;
  }, [decide]);

  const handleStackDecide = useCallback(
    (decision: DecisionValue, source: DecisionSource) => {
      if (!currentItem) return;
      // Every non-auto trigger (swipe/tap/keyboard) is recorded the same
      // way server-side — there is no separate `decided_via` per input
      // method, only "a person decided this now" (`swipe`) vs. "the
      // default-behavior timeout decided it" (`auto`, see onFinished
      // above) vs. "undone from the saved list" (`manual_remove`,
      // handled by useRemoveSaved instead). `source` still reaches the
      // backend indirectly, in spirit, via this always-"swipe" mapping.
      void source;
      decide(currentItem.pmid, decision, "swipe");
    },
    [currentItem, decide],
  );

  // Mirror the playback engine's own status into the Zustand store that
  // the UI actually reads (§11.2) — the engine (§11.3) stays the one
  // source of truth for *whether* speech is playing; this store is a
  // read-only reflection of it for components, never an independently
  // toggled duplicate of the same fact.
  useEffect(() => {
    if (engine.status === "playing") {
      playback.play();
    } else {
      playback.pause();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engine.status]);

  const handleTogglePlay = useCallback(() => {
    if (engine.status === "playing") {
      engine.pause();
    } else {
      engine.play();
    }
  }, [engine]);

  const handleStart = useCallback(() => {
    runSearch.mutate(
      {
        query: draft.query,
        sort: draft.sort,
        read_aloud_fields: draft.readAloudFields,
        default_swipe_behavior: draft.defaultSwipeBehavior,
        speed: draft.speed,
      },
      { onSuccess: () => openStack() },
    );
  }, [draft, runSearch, openStack]);

  return (
    <>
      <CookieConsentNotice />
      <PendingRetryBanner />

      {activePanel === "search" ? (
        <SearchSettingsPanel
          settings={{
            query: draft.query,
            sort: draft.sort,
            read_aloud_fields: draft.readAloudFields,
            default_swipe_behavior: draft.defaultSwipeBehavior,
            speed: draft.speed,
          }}
          onQueryChange={draft.setQuery}
          onSortChange={draft.setSort}
          onReadAloudFieldToggle={draft.toggleReadAloudField}
          onDefaultSwipeBehaviorChange={draft.setDefaultSwipeBehavior}
          onSpeedChange={draft.setSpeed}
          onClose={openStack}
          onStart={handleStart}
          isLoading={runSearch.isPending}
          error={apiErrorOrNull(runSearch.error)}
          isOffline={isOffline}
          onRetry={handleStart}
        />
      ) : null}

      {activePanel === "saved" ? (
        <SavedListPanel
          savedPapers={saved.data?.items ?? []}
          isZoteroConnected={zoteroCollections.data?.connected ?? false}
          onRemove={(pmid) => removeSaved.mutate(pmid)}
          // Screen D1's real push sub-flow (§5.5) is `<ZoteroPushModal />`
          // (Task 4B, `features/zotero/`), mounted once below — this
          // button only needs to open it.
          onPushToZotero={openZoteroPushFlow}
          onDownloadCsv={() => {
            window.location.href = getExportCsvUrl();
          }}
          onDisconnectZotero={handleDisconnectZotero}
          onClose={openStack}
        />
      ) : null}

      <ZoteroPushModal />

      {activePanel === "stack" ? (
        !hasSearchedThisVisit ? (
          <IdleScreen
            hasSavedItems={(saved.data?.items.length ?? 0) > 0}
            onOpenSearch={openSearch}
            onOpenSaved={openSaved}
          />
        ) : queue.isLoading ? null : queue.isError ? (
          // §13.6/§4.5: `GET /queue` itself failed (PubMed down with
          // nothing cached yet, or the request never reached the network
          // at all) — previously this fell through to the zero-result
          // `EmptyQueueState`'s misleading "no papers matched" copy.
          // Distinct surface, real retry.
          <ErrorState
            error={apiErrorOrNull(queue.error)}
            isOffline={isOffline}
            onRetry={() => void queue.refetch()}
          />
        ) : (queue.data?.items.length ?? 0) === 0 ? (
          <EmptyQueueState query={draft.query} onOpenSearch={openSearch} />
        ) : currentItem ? (
          currentAbstract.isError ? (
            // The queue itself is fine, but the current card's abstract
            // (and therefore its narration) couldn't be fetched —
            // surfaced here rather than silently rendering a card with
            // no abstract/no narration content.
            <ErrorState
              error={apiErrorOrNull(currentAbstract.error)}
              isOffline={isOffline}
              onRetry={() => void currentAbstract.refetch()}
            />
          ) : (
            // `key={currentItem.pmid}` forces a fresh `StackScreen`
            // (and therefore a fresh `useSwipeToDecide`) instance per
            // paper — the swipe-gesture hook's internal re-entrancy
            // guard is scoped to one card's lifetime this way, rather
            // than needing an explicit reset signal threaded down.
            <StackScreen
              key={currentItem.pmid}
              currentPaper={currentItem}
              nextPaper={nextItem}
              segments={currentAbstract.data?.segments ?? []}
              highlightedIndex={playback.highlightedSegmentIndex}
              isPlaying={playback.isPlaying}
              isMuted={playback.isMuted}
              onDecide={handleStackDecide}
              onTogglePlay={handleTogglePlay}
              onToggleMute={playback.toggleMute}
              onOpenSearch={openSearch}
              onOpenSaved={openSaved}
              isDecisionPending={updateDecision.isPending}
            />
          )
        ) : (
          // A queue exists but every item has already been decided —
          // reuse the same "nothing to play" surface as a zero-result
          // search (SPEC.md doesn't distinguish these two "nothing
          // current to show" states with separate copy).
          <EmptyQueueState query={draft.query} onOpenSearch={openSearch} />
        )
      ) : null}
    </>
  );
}

export default App;
