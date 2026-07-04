/**
 * Screen B — Search & Settings Panel (SPEC.md §5.2).
 *
 * Fully controlled/presentational: the parent owns `settings` state (in
 * Zustand as in-progress unsaved edits, per §11.2) and passes it down
 * along with change handlers. No TanStack Query / network calls here.
 */
import type { SearchSettings, SortOption } from "./types";

export interface SearchSettingsPanelProps {
  settings: SearchSettings;
  onQueryChange: (query: string) => void;
  onSortChange: (sort: SortOption) => void;
  onReadAloudFieldToggle: (
    field: keyof SearchSettings["read_aloud_fields"],
  ) => void;
  onDefaultSwipeBehaviorChange: (
    value: SearchSettings["default_swipe_behavior"],
  ) => void;
  onSpeedChange: (speed: number) => void;
  onClose: () => void;
  onStart: () => void;
  /** §5.2's inline spinner near the search field — never a full-screen
   *  blocker, per §5.6's "loading states never block gesture input." */
  isLoading?: boolean;
}

export function SearchSettingsPanel({
  settings,
  onQueryChange,
  onSortChange,
  onReadAloudFieldToggle,
  onDefaultSwipeBehaviorChange,
  onSpeedChange,
  onClose,
  onStart,
  isLoading = false,
}: SearchSettingsPanelProps) {
  const queryIsBlank = settings.query.trim().length === 0;

  return (
    <div className="flex min-h-screen flex-col gap-4 bg-white p-4 text-slate-900">
      <div className="flex items-center justify-between">
        <button type="button" aria-label="Close search and settings" onClick={onClose}>
          ✕
        </button>
        <button type="button" aria-label="Collapse (swipe up)" onClick={onClose} className="text-sm text-slate-500">
          swipe ⌃
        </button>
      </div>

      <div className="flex items-center gap-2">
        <label htmlFor="search-query" className="sr-only">
          Search PubMed
        </label>
        <input
          id="search-query"
          type="search"
          autoFocus
          value={settings.query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="🔍 computational neuro..."
          className="flex-1 rounded border border-slate-300 px-3 py-2"
        />
        {isLoading ? (
          <span role="status" aria-label="Searching" data-testid="search-loading-spinner">
            ⏳
          </span>
        ) : null}
      </div>

      <fieldset>
        <legend className="text-sm font-medium">Sort by:</legend>
        {(
          [
            ["relevance", "Relevance"],
            ["recency", "Recency"],
            ["citations", "Citations"],
          ] as [SortOption, string][]
        ).map(([value, label]) => (
          <label key={value} className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="sort"
              value={value}
              checked={settings.sort === value}
              onChange={() => onSortChange(value)}
            />
            {label}
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend className="text-sm font-medium">Read aloud:</legend>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={settings.read_aloud_fields.last_author}
            onChange={() => onReadAloudFieldToggle("last_author")}
          />
          Last author
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={settings.read_aloud_fields.all_authors}
            onChange={() => onReadAloudFieldToggle("all_authors")}
          />
          All authors
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={settings.read_aloud_fields.journal}
            onChange={() => onReadAloudFieldToggle("journal")}
          />
          Journal
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={settings.read_aloud_fields.pub_date}
            onChange={() => onReadAloudFieldToggle("pub_date")}
          />
          Publication date
        </label>
      </fieldset>

      <fieldset>
        <legend className="text-sm font-medium">If I don&apos;t swipe:</legend>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            name="default-swipe"
            checked={settings.default_swipe_behavior === "interested"}
            onChange={() => onDefaultSwipeBehaviorChange("interested")}
          />
          Mark Interested
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            name="default-swipe"
            checked={settings.default_swipe_behavior === "not_interested"}
            onChange={() => onDefaultSwipeBehaviorChange("not_interested")}
          />
          Mark Not Interested
        </label>
      </fieldset>

      <div>
        <label htmlFor="speed-slider" className="text-sm font-medium">
          Speed
        </label>
        <input
          id="speed-slider"
          type="range"
          min={0.5}
          max={2}
          step={0.1}
          value={settings.speed}
          onChange={(event) => onSpeedChange(Number(event.target.value))}
        />
        <span>{settings.speed.toFixed(1)}x</span>
      </div>

      <fieldset>
        <legend className="text-sm font-medium">Format:</legend>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" name="format" checked readOnly />
          Audiobook (TTS)
        </label>
        <label
          className="flex items-center gap-2 text-sm text-slate-400"
          title="coming later"
        >
          <input type="radio" name="format" disabled />
          Podcast (soon)
        </label>
      </fieldset>

      <button
        type="button"
        onClick={onStart}
        disabled={queryIsBlank}
        className="rounded bg-slate-900 px-4 py-2 font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        Start ▶
      </button>
    </div>
  );
}
