import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ErrorState } from "./ErrorState";

describe("ErrorState (Task 4C, §11.7)", () => {
  it("renders as an alert with the generic-context copy by default", () => {
    render(<ErrorState error={{ code: "internal_error", message: "Oops." }} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Oops.");
  });

  it("§13.6: shows external-unavailable copy distinct from §4.5 offline copy, and does not itself claim the app is offline", () => {
    render(
      <ErrorState
        error={{ code: "service_unavailable", message: "PubMed is currently unavailable." }}
        isOffline={false}
      />,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/temporarily unavailable/i);
    expect(alert).not.toHaveTextContent(/you're offline/i);
    expect(alert.dataset.code).toBe("service_unavailable");
  });

  it("§4.5: shows offline copy when isOffline is true, regardless of context", () => {
    render(<ErrorState isOffline />);
    expect(screen.getByRole("alert")).toHaveTextContent(/you're offline/i);
  });

  it("§4.4/§5.5: zotero_push context always offers a CSV fallback alongside retry", () => {
    const onRetry = vi.fn();
    const onDownloadCsv = vi.fn();
    render(
      <ErrorState
        context="zotero_push"
        error={{ code: "internal_error", message: "" }}
        onRetry={onRetry}
        onDownloadCsv={onDownloadCsv}
      />,
    );
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download csv/i })).toBeInTheDocument();
  });

  it("calls onRetry when the retry button is clicked, and labels it 'Retry now' while offline", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<ErrorState isOffline onRetry={onRetry} />);
    const button = screen.getByRole("button", { name: /retry now/i });
    await user.click(button);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("renders no action buttons when neither onRetry nor onDownloadCsv is provided", () => {
    render(<ErrorState error={{ code: "not_found", message: "Not found." }} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("§5.3a: empty_results context names the query, and supports a custom retryLabel over the default 'Retry' wording", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <ErrorState
        context="empty_results"
        query="asdkjalksdj 12931"
        onRetry={onRetry}
        retryLabel="Swipe down to try a different search."
      />,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/no papers matched/i);
    expect(alert).toHaveTextContent(/asdkjalksdj 12931/);

    const button = screen.getByRole("button", { name: /try a different search/i });
    expect(screen.queryByRole("button", { name: /^retry$/i })).not.toBeInTheDocument();
    await user.click(button);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("Task 4B post-review fix: retryDisabled disables the retry button without hiding it or the CSV fallback", () => {
    const onRetry = vi.fn();
    const onDownloadCsv = vi.fn();
    render(
      <ErrorState
        context="zotero_push"
        error={{ code: "internal_error", message: "" }}
        onRetry={onRetry}
        onDownloadCsv={onDownloadCsv}
        retryDisabled
      />,
    );
    expect(screen.getByRole("button", { name: /retry/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /download csv/i })).toBeEnabled();
  });
});
