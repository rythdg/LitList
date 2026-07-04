import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { paperNormal, paperRetracted } from "./fixtures";
import { SavedListPanel } from "./SavedListPanel";

function baseProps(overrides: Partial<React.ComponentProps<typeof SavedListPanel>> = {}) {
  return {
    savedPapers: [paperNormal],
    isZoteroConnected: false,
    onRemove: vi.fn(),
    onPushToZotero: vi.fn(),
    onDownloadCsv: vi.fn(),
    onDisconnectZotero: vi.fn(),
    onClose: vi.fn(),
    ...overrides,
  };
}

describe("SavedListPanel (§5.4)", () => {
  it("shows the empty-state copy and disables export buttons when nothing is saved", () => {
    render(<SavedListPanel {...baseProps({ savedPapers: [] })} />);
    expect(screen.getByTestId("saved-empty-copy")).toHaveTextContent(
      "Papers you mark Interested will show up here.",
    );
    expect(screen.getByRole("button", { name: /push to zotero/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /download csv/i })).toBeDisabled();
  });

  it("only shows Disconnect Zotero once a ZoteroConnection exists (§9.6)", () => {
    const { rerender } = render(<SavedListPanel {...baseProps({ isZoteroConnected: false })} />);
    expect(screen.queryByTestId("disconnect-zotero-button")).not.toBeInTheDocument();

    rerender(<SavedListPanel {...baseProps({ isZoteroConnected: true })} />);
    expect(screen.getByTestId("disconnect-zotero-button")).toBeInTheDocument();
  });

  it("deletes the Zotero connection immediately when Disconnect Zotero is activated", async () => {
    const onDisconnectZotero = vi.fn();
    render(
      <SavedListPanel
        {...baseProps({ isZoteroConnected: true, onDisconnectZotero })}
      />,
    );
    await userEvent.click(screen.getByTestId("disconnect-zotero-button"));
    expect(onDisconnectZotero).toHaveBeenCalledOnce();
  });

  it("shows the ⚠ Retracted badge for a saved retracted paper (§13.4)", () => {
    render(<SavedListPanel {...baseProps({ savedPapers: [paperRetracted] })} />);
    expect(
      screen.getByTestId(`retracted-badge-${paperRetracted.pmid}`),
    ).toHaveTextContent("⚠ Retracted");
  });

  it("calls onRemove for the item's [✕], not reopening the card in the queue (§4.7)", async () => {
    const onRemove = vi.fn();
    render(<SavedListPanel {...baseProps({ onRemove })} />);
    await userEvent.click(
      screen.getByRole("button", { name: new RegExp(`remove ${paperNormal.title}`, "i") }),
    );
    expect(onRemove).toHaveBeenCalledWith(paperNormal.pmid);
  });
});
