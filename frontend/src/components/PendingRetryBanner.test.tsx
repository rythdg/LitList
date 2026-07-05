import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PendingRetryBanner } from "./PendingRetryBanner";
import { useRetryQueueStore } from "../state/retryQueueStore";

/**
 * Adversarial-review fix (Finding 2, "TASK 4C SEC15.6 FOLLOW-UP
 * REVIEW"): before this component existed, `retryQueueStore` had no
 * reader anywhere in the app — a queued-but-not-yet-saved decision was
 * genuinely indistinguishable from a saved one. These tests prove the
 * banner actually renders `retryQueueStore`'s real state (not a copy of
 * it) and that its two affordances (manual retry, dismiss a failure)
 * call the store's real actions.
 */
describe("PendingRetryBanner (§4.5 point 4, adversarial-review Finding 2)", () => {
  beforeEach(() => {
    useRetryQueueStore.setState({ items: [], failedItems: [], isRetrying: false });
  });

  it("renders nothing when the queue is empty and there are no failures", () => {
    render(<PendingRetryBanner />);
    expect(screen.queryByTestId("pending-retry-banner")).not.toBeInTheDocument();
    expect(screen.queryByTestId("failed-retry-item")).not.toBeInTheDocument();
  });

  it("shows a pending count when retryQueueStore has queued items — the user-visible signal a queued decision hasn't actually saved yet", () => {
    useRetryQueueStore.getState().enqueue({
      id: "decision-1",
      label: "Save decision for paper 1",
      run: vi.fn(),
    });

    render(<PendingRetryBanner />);
    const banner = screen.getByTestId("pending-retry-banner");
    expect(banner).toHaveTextContent(/1 change is pending/i);
    expect(banner).toHaveTextContent(/will retry when back online/i);
  });

  it("pluralizes for more than one pending item", () => {
    useRetryQueueStore.getState().enqueue({ id: "a", label: "a", run: vi.fn() });
    useRetryQueueStore.getState().enqueue({ id: "b", label: "b", run: vi.fn() });

    render(<PendingRetryBanner />);
    expect(screen.getByTestId("pending-retry-banner")).toHaveTextContent(/2 changes are pending/i);
  });

  it("'Retry now' calls the real retryQueueStore.retryAll(), not a local no-op", async () => {
    const user = userEvent.setup();
    const run = vi.fn().mockResolvedValue(undefined);
    useRetryQueueStore.getState().enqueue({ id: "decision-1", label: "Save decision", run });

    render(<PendingRetryBanner />);
    await user.click(screen.getByRole("button", { name: /retry now/i }));

    expect(run).toHaveBeenCalledTimes(1);
  });

  it("renders a failed item distinctly from a pending one, with its message, once retryQueueStore surfaces a permanent failure", () => {
    useRetryQueueStore.setState({
      items: [],
      failedItems: [{ id: "decision-1", label: "Save decision for paper 1", message: "Decision not found." }],
      isRetrying: false,
    });

    render(<PendingRetryBanner />);
    expect(screen.queryByTestId("pending-retry-banner")).not.toBeInTheDocument();
    const failed = screen.getByTestId("failed-retry-item");
    expect(failed).toHaveTextContent(/couldn.t save/i);
    expect(failed).toHaveTextContent(/save decision for paper 1/i);
    expect(failed).toHaveTextContent(/decision not found/i);
  });

  it("'Dismiss' calls the real retryQueueStore.dismissFailed() for that specific item", async () => {
    const user = userEvent.setup();
    useRetryQueueStore.setState({
      items: [],
      failedItems: [
        { id: "decision-1", label: "Save decision for paper 1", message: "Decision not found." },
        { id: "decision-2", label: "Save decision for paper 2", message: "Decision not found." },
      ],
      isRetrying: false,
    });

    render(<PendingRetryBanner />);
    await user.click(screen.getByRole("button", { name: /dismiss failed: save decision for paper 1/i }));

    expect(useRetryQueueStore.getState().failedItems.map((item) => item.id)).toEqual(["decision-2"]);
  });
});
