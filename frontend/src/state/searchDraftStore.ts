import { create } from "zustand";
import type { DecisionValue, ReadAloudField, SortOrder } from "../api/types";

/**
 * In-progress (unsaved) edits to the Search & Settings panel (§5.2, §11.2)
 * — this is *not* the committed `SearchSession` (that lives in TanStack
 * Query, seeded from `GET /search/settings` and updated only once the
 * user taps "Start", per §3.5). Editing a field here never touches the
 * backend; only `commitToSearch` (called by the component that fires
 * `useRunSearch`, api/search.ts) turns a draft into a real search.
 */
export interface SearchDraftState {
  query: string;
  sort: SortOrder;
  readAloudFields: ReadAloudField[];
  defaultSwipeBehavior: Extract<DecisionValue, "interested" | "not_interested">;
  speed: number;

  setQuery: (query: string) => void;
  setSort: (sort: SortOrder) => void;
  toggleReadAloudField: (field: ReadAloudField) => void;
  setDefaultSwipeBehavior: (value: Extract<DecisionValue, "interested" | "not_interested">) => void;
  setSpeed: (speed: number) => void;
  /** Overwrite the whole draft at once — used to pre-fill the panel from
   * `GET /search/settings` (§3.5) the first time it's opened this visit. */
  hydrate: (values: Omit<SearchDraftState, keyof SearchDraftActions>) => void;
}

type SearchDraftActions = Pick<
  SearchDraftState,
  "setQuery" | "setSort" | "toggleReadAloudField" | "setDefaultSwipeBehavior" | "setSpeed" | "hydrate"
>;

const DEFAULTS: Omit<SearchDraftState, keyof SearchDraftActions> = {
  query: "",
  sort: "relevance",
  readAloudFields: [],
  defaultSwipeBehavior: "not_interested",
  speed: 1,
};

export const useSearchDraftStore = create<SearchDraftState>((set) => ({
  ...DEFAULTS,

  setQuery: (query) => set({ query }),
  setSort: (sort) => set({ sort }),
  toggleReadAloudField: (field) =>
    set((state) => ({
      readAloudFields: state.readAloudFields.includes(field)
        ? state.readAloudFields.filter((f) => f !== field)
        : [...state.readAloudFields, field],
    })),
  setDefaultSwipeBehavior: (defaultSwipeBehavior) => set({ defaultSwipeBehavior }),
  setSpeed: (speed) => set({ speed }),
  hydrate: (values) => set({ ...values }),
}));
