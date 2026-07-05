import { afterEach, describe, expect, it, vi } from "vitest";
import { ZOTERO_REOPEN_FLAG_KEY } from "./zoteroPushFlowStore";

/**
 * `useZoteroPushFlowStore`'s one-shot sessionStorage-flag consumption
 * happens at *module init time* (see the store's own docstring for why
 * — it has to happen once per real page load, matching the OAuth
 * round-trip's hard-navigation boundary). Testing that requires a fresh
 * module instance per scenario, so this file uses `vi.resetModules()` +
 * dynamic `import()` per test rather than the usual static import — and
 * imports `./panelStore` *through the same dynamic import graph* (not
 * the module-scope static import used elsewhere) so both stores share
 * one fresh module instance per test rather than the panel-store check
 * silently reading a stale, pre-reset module.
 */
describe("useZoteroPushFlowStore (§11.2 local-only UI state, Task 4B)", () => {
  afterEach(() => {
    sessionStorage.clear();
    vi.resetModules();
  });

  it("starts closed and toggles via open()/close()", async () => {
    const { useZoteroPushFlowStore } = await import("./zoteroPushFlowStore");
    expect(useZoteroPushFlowStore.getState().isOpen).toBe(false);
    useZoteroPushFlowStore.getState().open();
    expect(useZoteroPushFlowStore.getState().isOpen).toBe(true);
    useZoteroPushFlowStore.getState().close();
    expect(useZoteroPushFlowStore.getState().isOpen).toBe(false);
  });

  it("starts open, consumes (clears) the flag, and opens the Saved panel when the OAuth reopen flag is present", async () => {
    sessionStorage.setItem(ZOTERO_REOPEN_FLAG_KEY, "1");
    const { useZoteroPushFlowStore } = await import("./zoteroPushFlowStore");
    const { usePanelStore } = await import("./panelStore");
    expect(useZoteroPushFlowStore.getState().isOpen).toBe(true);
    expect(sessionStorage.getItem(ZOTERO_REOPEN_FLAG_KEY)).toBeNull();
    expect(usePanelStore.getState().activePanel).toBe("saved");
  });

  it("starts closed and never touches the panel when no reopen flag is present", async () => {
    const { useZoteroPushFlowStore } = await import("./zoteroPushFlowStore");
    const { usePanelStore } = await import("./panelStore");
    expect(useZoteroPushFlowStore.getState().isOpen).toBe(false);
    expect(usePanelStore.getState().activePanel).toBe("stack");
  });

  it("starts with isPushPending false and toggles via setPushPending (Task 4B post-review fix)", async () => {
    const { useZoteroPushFlowStore } = await import("./zoteroPushFlowStore");
    expect(useZoteroPushFlowStore.getState().isPushPending).toBe(false);
    useZoteroPushFlowStore.getState().setPushPending(true);
    expect(useZoteroPushFlowStore.getState().isPushPending).toBe(true);
    useZoteroPushFlowStore.getState().setPushPending(false);
    expect(useZoteroPushFlowStore.getState().isPushPending).toBe(false);
  });
});
