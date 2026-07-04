import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ZoteroPushFlow, type ZoteroPushFlowProps } from "./ZoteroPushFlow";

const collections = [
  { key: "AAA111", name: "Reading List" },
  { key: "BBB222", name: "Neuro Journal Club" },
];

function baseProps(overrides: Partial<ZoteroPushFlowProps> = {}): ZoteroPushFlowProps {
  return {
    step: "connect",
    paperCount: 7,
    collections,
    selectedCollectionKey: null,
    onSelectCollection: vi.fn(),
    onCreateCollection: vi.fn(),
    onConnect: vi.fn(),
    onCancel: vi.fn(),
    onSave: vi.fn(),
    onRetry: vi.fn(),
    onDownloadCsv: vi.fn(),
    onDone: vi.fn(),
    ...overrides,
  };
}

describe("ZoteroPushFlow (§5.5)", () => {
  it("Step 1: prompts to connect when not yet connected", () => {
    render(<ZoteroPushFlow {...baseProps({ step: "connect" })} />);
    expect(screen.getByTestId("zotero-step-connect")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /connect to zotero/i }),
    ).toBeInTheDocument();
  });

  it("Step 2: lists collections plus a '+ New collection...' option", () => {
    render(<ZoteroPushFlow {...baseProps({ step: "choose_collection" })} />);
    expect(screen.getByText(/save 7 papers to/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Reading List")).toBeInTheDocument();
    expect(screen.getByLabelText("Neuro Journal Club")).toBeInTheDocument();
    expect(screen.getByLabelText(/new collection/i)).toBeInTheDocument();
  });

  it("Step 2 offline: shows the pending/retry variant instead of Save (§5's offline resolution)", () => {
    render(
      <ZoteroPushFlow {...baseProps({ step: "choose_collection", isOffline: true })} />,
    );
    expect(screen.getByTestId("zotero-pending-retry")).toHaveTextContent(
      /pending.*retry when back online/i,
    );
    expect(screen.queryByRole("button", { name: /^save$/i })).not.toBeInTheDocument();
  });

  it("Step 3a: shows success copy naming the collection/count", () => {
    render(<ZoteroPushFlow {...baseProps({ step: "success" })} />);
    expect(screen.getByTestId("zotero-step-success")).toHaveTextContent(
      /saved 7 papers/i,
    );
  });

  it("Step 3b (error state): distinguishes push failure from connection failure and always offers CSV fallback", () => {
    const { rerender } = render(
      <ZoteroPushFlow {...baseProps({ step: "failure", failureReason: "push" })} />,
    );
    expect(screen.getByTestId("zotero-step-failure")).toHaveTextContent(
      /couldn't save to zotero/i,
    );
    expect(screen.getByRole("button", { name: /download csv/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();

    rerender(
      <ZoteroPushFlow {...baseProps({ step: "failure", failureReason: "connection" })} />,
    );
    expect(screen.getByTestId("zotero-step-failure")).toHaveTextContent(
      /couldn't connect to zotero/i,
    );
  });

  it("expands an inline text field for '+ New collection...' rather than navigating away", async () => {
    render(
      <ZoteroPushFlow
        {...baseProps({ step: "choose_collection", selectedCollectionKey: "__new__" })}
      />,
    );
    expect(screen.getByLabelText(/new collection name/i)).toBeInTheDocument();
  });
});
