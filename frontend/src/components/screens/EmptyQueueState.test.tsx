import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EmptyQueueState } from "./EmptyQueueState";

describe("EmptyQueueState (§5.3a empty-result state)", () => {
  it("shows the no-results copy including the failed query and a disabled play button", () => {
    render(
      <EmptyQueueState query="asdkjalksdj 12931" onOpenSearch={vi.fn()} />,
    );
    expect(screen.getByText(/no papers matched/i)).toBeInTheDocument();
    expect(screen.getByText(/asdkjalksdj 12931/)).toBeInTheDocument();
    expect(screen.getByTestId("disabled-play-button")).toBeDisabled();
  });

  it("only the swipe-down/search affordance is live", async () => {
    const onOpenSearch = vi.fn();
    render(<EmptyQueueState query="x" onOpenSearch={onOpenSearch} />);
    await userEvent.click(
      screen.getByRole("button", { name: /try a different search/i }),
    );
    expect(onOpenSearch).toHaveBeenCalledOnce();
  });
});
