import { beforeEach, describe, expect, it } from "vitest";
import { useUiStore } from "./uiStore";

const initialState = useUiStore.getInitialState();

describe("useUiStore (§10.2/§11.2 cookie-consent notice dismissal)", () => {
  beforeEach(() => {
    useUiStore.setState(initialState, true);
  });

  it("starts un-dismissed", () => {
    expect(useUiStore.getState().isCookieNoticeDismissed).toBe(false);
  });

  it("dismissCookieNotice sets dismissed to true and stays true", () => {
    useUiStore.getState().dismissCookieNotice();
    expect(useUiStore.getState().isCookieNoticeDismissed).toBe(true);
  });
});
