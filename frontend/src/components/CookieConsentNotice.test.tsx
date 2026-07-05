import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { CookieConsentNotice } from "./CookieConsentNotice";
import { useUiStore } from "../state/uiStore";

const initialState = useUiStore.getInitialState();

describe("CookieConsentNotice (§10.2, §11.7)", () => {
  beforeEach(() => {
    useUiStore.setState(initialState, true);
  });

  it("shows the specific, honest copy naming the cookie's actual purpose (not generic boilerplate)", () => {
    render(<CookieConsentNotice />);
    const notice = screen.getByTestId("cookie-consent-notice");
    expect(notice).toHaveTextContent(/one cookie/i);
    expect(notice).toHaveTextContent(/no tracking, no ads/i);
    expect(notice).toHaveTextContent(/zotero/i);
  });

  it("dismisses via uiStore and does not re-render once dismissed", async () => {
    const user = userEvent.setup();
    render(<CookieConsentNotice />);
    await user.click(screen.getByRole("button", { name: /dismiss cookie notice/i }));

    expect(useUiStore.getState().isCookieNoticeDismissed).toBe(true);
    expect(screen.queryByTestId("cookie-consent-notice")).not.toBeInTheDocument();
  });

  it("renders nothing when already dismissed (e.g. a later mount in the same session)", () => {
    useUiStore.getState().dismissCookieNotice();
    render(<CookieConsentNotice />);
    expect(screen.queryByTestId("cookie-consent-notice")).not.toBeInTheDocument();
  });

  it("is not a functionality gate — the notice is purely informational per §11.7", () => {
    // No functionality prop exists on this component to gate; this test
    // documents the intent so a future change doesn't accidentally wire
    // one in without a deliberate SPEC.md update.
    render(<CookieConsentNotice />);
    expect(screen.getByTestId("cookie-consent-notice")).toBeInTheDocument();
  });
});
