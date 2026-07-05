import { afterEach, describe, expect, it } from "vitest";
import { useNetworkStore } from "./networkStore";

describe("networkStore (§4.5, §11.5)", () => {
  afterEach(() => {
    useNetworkStore.setState({ isOnline: true });
  });

  it("defaults to navigator.onLine", () => {
    expect(useNetworkStore.getState().isOnline).toBe(true);
  });

  it("setOnline updates the store directly, independent of any error code", () => {
    useNetworkStore.getState().setOnline(false);
    expect(useNetworkStore.getState().isOnline).toBe(false);
    useNetworkStore.getState().setOnline(true);
    expect(useNetworkStore.getState().isOnline).toBe(true);
  });
});
