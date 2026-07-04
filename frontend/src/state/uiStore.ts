import { create } from "zustand";

/**
 * Miscellaneous UI-only state with no backend counterpart (§11.2):
 * whether the cookie-consent notice (§10.2) has been dismissed this
 * session. Deliberately in-memory only (per-session, not persisted) —
 * §10.2 describes this as a "brief, honest, one-time notice," and
 * nothing in SPEC.md asks for it to survive a hard reload.
 */
export interface UiState {
  isCookieNoticeDismissed: boolean;
  dismissCookieNotice: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  isCookieNoticeDismissed: false,
  dismissCookieNotice: () => set({ isCookieNoticeDismissed: true }),
}));
