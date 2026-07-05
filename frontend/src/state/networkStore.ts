import { create } from "zustand";

/**
 * Local-only (§11.2) connectivity state: whether *this device* currently
 * has a network connection, per SPEC.md §4.5/§11.5. This is deliberately
 * separate from CONTRACTS.md §2's `service_unavailable` error code
 * (§13.6) — that code means an *external* dependency (PubMed/iCite/
 * Zotero) is down while the user's own connection is fine, which is a
 * different condition calling for different copy (Task 4C's brief). This
 * store must never be flipped to `false` just because a request came
 * back with `service_unavailable` — only real browser online/offline
 * signals (see `offlineSync.ts`) update it.
 */
export interface NetworkState {
  isOnline: boolean;
  setOnline: (online: boolean) => void;
}

function initialOnlineState(): boolean {
  return typeof navigator === "undefined" ? true : navigator.onLine;
}

export const useNetworkStore = create<NetworkState>((set) => ({
  isOnline: initialOnlineState(),
  setOnline: (online) => set({ isOnline: online }),
}));
