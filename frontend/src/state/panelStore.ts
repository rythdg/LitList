import { create } from "zustand";

/**
 * Which of the three vertically-stacked panels (§3.3) is currently
 * visible. Purely a UI concern — no backend counterpart (§11.2) — driven
 * by swipe/tap gestures rather than a route, per §11.6's decision that
 * this app is one SPA state machine, not a set of routed pages (the one
 * exception, the Zotero OAuth callback, is a real route owned by Task 2A).
 */
export type Panel = "search" | "stack" | "saved";

export interface PanelState {
  activePanel: Panel;
  openSearch: () => void;
  openStack: () => void;
  openSaved: () => void;
  setPanel: (panel: Panel) => void;
}

export const usePanelStore = create<PanelState>((set) => ({
  activePanel: "stack",
  openSearch: () => set({ activePanel: "search" }),
  openStack: () => set({ activePanel: "stack" }),
  openSaved: () => set({ activePanel: "saved" }),
  setPanel: (panel) => set({ activePanel: panel }),
}));
