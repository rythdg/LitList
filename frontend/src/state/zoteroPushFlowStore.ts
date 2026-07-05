import { create } from "zustand";
import { usePanelStore } from "./panelStore";

/**
 * Local-only (§11.2) UI state: whether the Zotero push sub-flow modal
 * (SPEC.md §5.5, `ZoteroPushFlow.tsx`) is open. Task 4B.
 *
 * **The OAuth round-trip hand-off (§8.2 step 6).** `GET /zotero/auth/
 * callback`'s redirect (Task 3B/4B, see CONTRACTS.md §6) lands the
 * browser on `ZoteroCallbackRoute.tsx` via a real, hard page navigation
 * — every in-memory store (this one included) starts fresh at that
 * point, so "please reopen the push flow once we're back in the app"
 * can't be conveyed via a direct store call from the callback route; it
 * has to survive the reload. `ZoteroCallbackRoute.tsx` writes a
 * one-shot `sessionStorage` flag before handing off back to the SPA
 * (`goHome()`); this store consumes (reads-and-clears) that flag exactly
 * once, at module-init time, which happens once per real page load —
 * matching the "once per OAuth round-trip" semantics needed here. If
 * nothing mounts this store on that page load (e.g. Zotero wiring isn't
 * yet composed into `App.tsx`), the flag is simply never read and the
 * saved list still shows "Connected to Zotero" via `useZoteroCollections`
 * on next render — this is a convenience auto-open, not the only way the
 * connection takes effect.
 */
export const ZOTERO_REOPEN_FLAG_KEY = "litlist:zotero-just-connected";

export interface ZoteroPushFlowState {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  /** Mirrors `useZoteroPush()`'s own `isPending` (server-state, owned by
   *  TanStack Query — this is a read-only reflection of it, never an
   *  independently-toggled duplicate of the same fact, same pattern
   *  `App.tsx` already uses for the playback engine's status). Set by
   *  `useZoteroPushFlowController.ts` on every push attempt so *other*
   *  UI surfaces that don't render the push flow itself — namely the
   *  Saved List panel's "Disconnect Zotero" button, `App.tsx` — can
   *  still guard against racing an in-flight push (Task 4B, post-review
   *  fix: a push can complete and write to the user's real Zotero
   *  library even after a concurrent disconnect, so the UI must at
   *  least warn rather than silently allow it). */
  isPushPending: boolean;
  setPushPending: (pending: boolean) => void;
}

function consumeReopenFlag(): boolean {
  if (typeof sessionStorage === "undefined") {
    return false;
  }
  const flag = sessionStorage.getItem(ZOTERO_REOPEN_FLAG_KEY);
  if (!flag) {
    return false;
  }
  sessionStorage.removeItem(ZOTERO_REOPEN_FLAG_KEY);
  // Also surface the Saved List panel (§5.4) itself, since the push flow
  // is presented from there (§5.5) — otherwise "isOpen: true" would have
  // nothing visible to attach to if some other panel was active before
  // the user ever navigated away for the OAuth handshake.
  usePanelStore.getState().openSaved();
  return true;
}

export const useZoteroPushFlowStore = create<ZoteroPushFlowState>((set) => ({
  isOpen: consumeReopenFlag(),
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  isPushPending: false,
  setPushPending: (pending) => set({ isPushPending: pending }),
}));
