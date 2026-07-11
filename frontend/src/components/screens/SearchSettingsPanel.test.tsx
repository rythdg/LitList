import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { defaultSearchSettings } from "./fixtures";
import { SearchSettingsPanel } from "./SearchSettingsPanel";

function baseProps() {
  return {
    settings: defaultSearchSettings,
    onQueryChange: vi.fn(),
    onSortChange: vi.fn(),
    onReadAloudFieldToggle: vi.fn(),
    onDefaultSwipeBehaviorChange: vi.fn(),
    onSpeedChange: vi.fn(),
    onClose: vi.fn(),
    onStart: vi.fn(),
  };
}

describe("SearchSettingsPanel (§5.2)", () => {
  it("disables Start when the query is blank (validation per §5.2)", () => {
    render(<SearchSettingsPanel {...baseProps()} />);
    expect(screen.getByRole("button", { name: /start/i })).toBeDisabled();
  });

  it("enables Start once a query is present", () => {
    render(
      <SearchSettingsPanel
        {...baseProps()}
        settings={{ ...defaultSearchSettings, query: "computational neuro" }}
      />,
    );
    expect(screen.getByRole("button", { name: /start/i })).toBeEnabled();
  });

  it("shows the loading state as an inline spinner, not a full-screen blocker (§5.2/§5.6)", () => {
    render(<SearchSettingsPanel {...baseProps()} isLoading />);
    expect(screen.getByTestId("search-loading-spinner")).toBeInTheDocument();
    // Loading never disables the still-editable fields (§5.6: never blocks gesture input).
    expect(screen.getByLabelText(/search pubmed/i)).toBeEnabled();
  });

  // Task PERF-3: a live search can take 30-45s — while it's pending the
  // Start button must be disabled (no stacking concurrent searches) and
  // must say so visibly, not just via the small inline spinner.
  it("disables Start and relabels it 'Searching…' while a search is pending (PERF-3)", () => {
    render(
      <SearchSettingsPanel
        {...baseProps()}
        settings={{ ...defaultSearchSettings, query: "computational neuro" }}
        isLoading
      />,
    );
    const button = screen.getByRole("button", { name: /searching/i });
    expect(button).toBeDisabled();
    // The existing role="status" spinner is extended, not replaced.
    expect(screen.getByTestId("search-loading-spinner")).toBeInTheDocument();
    // And no "Start" button remains as a second, clickable submit path.
    expect(screen.queryByRole("button", { name: /start/i })).not.toBeInTheDocument();
  });

  it("does not show a spinner in the idle (non-loading) state", () => {
    render(<SearchSettingsPanel {...baseProps()} />);
    expect(screen.queryByTestId("search-loading-spinner")).not.toBeInTheDocument();
  });

  it("renders the Podcast format option as disabled with its 'coming later' affordance", () => {
    render(<SearchSettingsPanel {...baseProps()} />);
    const podcastRadio = screen.getByRole("radio", { name: /podcast/i });
    expect(podcastRadio).toBeDisabled();
  });
});
