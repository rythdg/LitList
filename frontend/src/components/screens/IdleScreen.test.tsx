import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { IdleScreen } from "./IdleScreen";

describe("IdleScreen (§5.1 idle state)", () => {
  it("renders the wordmark and disables the saved-list affordance when nothing is saved", () => {
    render(
      <IdleScreen
        hasSavedItems={false}
        onOpenSearch={vi.fn()}
        onOpenSaved={vi.fn()}
      />,
    );

    expect(screen.getByText("LitList")).toBeInTheDocument();
    const savedButton = screen.getByRole("button", {
      name: /swipe up for saved list/i,
    });
    expect(savedButton).toBeDisabled();
  });

  it("enables the saved-list affordance once something has been saved", () => {
    render(
      <IdleScreen
        hasSavedItems={true}
        onOpenSearch={vi.fn()}
        onOpenSaved={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: /swipe up for saved list/i }),
    ).toBeEnabled();
  });

  it("calls onOpenSearch via the tap-equivalent affordance", async () => {
    const onOpenSearch = vi.fn();
    render(
      <IdleScreen
        hasSavedItems={false}
        onOpenSearch={onOpenSearch}
        onOpenSaved={vi.fn()}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /swipe down to search/i }),
    );
    expect(onOpenSearch).toHaveBeenCalledOnce();
  });
});
