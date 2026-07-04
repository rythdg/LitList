import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { mockSegments, paperNormal, paperRetracted } from "./fixtures";
import { StackScreen } from "./StackScreen";

function baseProps(overrides: Partial<React.ComponentProps<typeof StackScreen>> = {}) {
  return {
    currentPaper: paperNormal,
    nextPaper: paperNormal,
    segments: mockSegments,
    highlightedIndex: null,
    isPlaying: false,
    isMuted: false,
    onDecide: vi.fn(),
    onTogglePlay: vi.fn(),
    onToggleMute: vi.fn(),
    onOpenSearch: vi.fn(),
    onOpenSaved: vi.fn(),
    ...overrides,
  };
}

describe("StackScreen (§5.3 stack surface)", () => {
  it("does not show the retracted badge for a normal paper", () => {
    render(<StackScreen {...baseProps()} />);
    expect(screen.queryByTestId("retracted-badge")).not.toBeInTheDocument();
  });

  it("shows the ⚠ Retracted badge when the paper's fixture data carries the flag (§13.4)", () => {
    render(<StackScreen {...baseProps({ currentPaper: paperRetracted })} />);
    expect(screen.getByTestId("retracted-badge")).toHaveTextContent(
      "⚠ Retracted",
    );
  });

  it("routes tap and keyboard decisions through the same onDecide callback (§11.4/§13.1)", async () => {
    const onDecide = vi.fn();
    render(<StackScreen {...baseProps({ onDecide })} />);

    await userEvent.click(screen.getByRole("button", { name: /^interested$/i }));
    expect(onDecide).toHaveBeenLastCalledWith("interested", "tap");

    await userEvent.click(screen.getByRole("button", { name: /^not interested$/i }));
    expect(onDecide).toHaveBeenLastCalledWith("not_interested", "tap");

    fireEvent.keyDown(document, { key: "ArrowRight" });
    expect(onDecide).toHaveBeenLastCalledWith("interested", "keyboard");

    fireEvent.keyDown(document, { key: "ArrowLeft" });
    expect(onDecide).toHaveBeenLastCalledWith("not_interested", "keyboard");
  });

  it("toggles play/pause via the space bar, matching the tap play button (§13.1)", () => {
    const onTogglePlay = vi.fn();
    render(<StackScreen {...baseProps({ onTogglePlay })} />);
    fireEvent.keyDown(document, { key: " " });
    expect(onTogglePlay).toHaveBeenCalledOnce();
  });

  it("keeps the abstract area collapsed/greyed until playback starts (§5.3)", () => {
    render(<StackScreen {...baseProps({ isPlaying: false })} />);
    expect(screen.getByTestId("abstract-area")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });

  it("reveals the abstract once playback starts", () => {
    render(<StackScreen {...baseProps({ isPlaying: true })} />);
    expect(screen.getByTestId("abstract-area")).toHaveAttribute(
      "aria-hidden",
      "false",
    );
  });

  // XSS regression test (§6.5/§11.3): title/abstract are untrusted external
  // PubMed text and must never be interpolated as raw HTML.
  it("never renders title or abstract text as executable/raw HTML", () => {
    const maliciousPaper = {
      ...paperNormal,
      title: '<img src=x onerror="window.__xss = true">',
    };
    const maliciousSegments = [
      {
        index: 0,
        kind: "sentence" as const,
        section_label: null,
        display_text: '<script>window.__xss = true;</script>',
        spoken_text: "harmless spoken text",
        char_start: 0,
        char_end: 10,
        pause_class: "sentence" as const,
      },
    ];

    const { container } = render(
      <StackScreen
        {...baseProps({
          currentPaper: maliciousPaper,
          segments: maliciousSegments,
          isPlaying: true,
        })}
      />,
    );

    // The raw markup was never parsed as HTML — no actual <img>/<script>
    // element exists in the rendered DOM, only escaped text nodes.
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect((window as unknown as { __xss?: boolean }).__xss).toBeUndefined();

    // The literal text is still visible on screen (safe framework escaping).
    expect(
      screen.getByText('<img src=x onerror="window.__xss = true">'),
    ).toBeInTheDocument();
    expect(screen.getByTestId("segment-0")).toHaveTextContent(
      "<script>window.__xss = true;</script>",
    );
  });
});
