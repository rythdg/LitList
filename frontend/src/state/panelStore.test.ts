import { beforeEach, describe, expect, it } from "vitest";
import { usePanelStore } from "./panelStore";

const initialState = usePanelStore.getInitialState();

describe("usePanelStore (§3.3/§11.2 which panel is open)", () => {
  beforeEach(() => {
    usePanelStore.setState(initialState, true);
  });

  it("defaults to the Stack Screen (§3.3's home surface)", () => {
    expect(usePanelStore.getState().activePanel).toBe("stack");
  });

  it("openSearch/openStack/openSaved switch the active panel", () => {
    usePanelStore.getState().openSearch();
    expect(usePanelStore.getState().activePanel).toBe("search");

    usePanelStore.getState().openSaved();
    expect(usePanelStore.getState().activePanel).toBe("saved");

    usePanelStore.getState().openStack();
    expect(usePanelStore.getState().activePanel).toBe("stack");
  });

  it("setPanel sets an arbitrary panel directly", () => {
    usePanelStore.getState().setPanel("search");
    expect(usePanelStore.getState().activePanel).toBe("search");
  });
});
