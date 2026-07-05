import { describe, expect, it } from "vitest";
import { getErrorCopy } from "./errorCopy";

describe("getErrorCopy (Task 4C, §11.7/§4.5/§13.6)", () => {
  it("returns distinct copy for offline vs. service_unavailable — the two must never collapse", () => {
    const offlineCopy = getErrorCopy({ isOffline: true });
    const serviceDownCopy = getErrorCopy({
      error: { code: "service_unavailable", message: "PubMed is currently unavailable." },
      isOffline: false,
    });

    expect(offlineCopy.title).not.toEqual(serviceDownCopy.title);
    expect(offlineCopy.message).not.toEqual(serviceDownCopy.message);
    expect(offlineCopy.title.toLowerCase()).toContain("offline");
    expect(serviceDownCopy.title.toLowerCase()).not.toContain("offline");
  });

  it("§4.5: offline copy wins even when a service_unavailable error is also present", () => {
    const copy = getErrorCopy({
      error: { code: "service_unavailable", message: "PubMed is down." },
      isOffline: true,
    });
    expect(copy.title.toLowerCase()).toContain("offline");
  });

  it("§13.6: service_unavailable copy surfaces the backend's own safe message", () => {
    const copy = getErrorCopy({
      error: { code: "service_unavailable", message: "iCite is currently unavailable. Please try again shortly." },
    });
    expect(copy.message).toBe("iCite is currently unavailable. Please try again shortly.");
  });

  it("§4.4/§5.5: zotero_push context distinguishes connection failure from push failure", () => {
    const connectionFailure = getErrorCopy({
      context: "zotero_push",
      error: { code: "zotero_not_connected", message: "" },
    });
    const pushFailure = getErrorCopy({
      context: "zotero_push",
      error: { code: "internal_error", message: "" },
    });
    expect(connectionFailure.title.toLowerCase()).toContain("connect");
    expect(pushFailure.title.toLowerCase()).toContain("save");
    expect(connectionFailure.title).not.toEqual(pushFailure.title);
  });

  it("§5.5: offline zotero_push copy says 'pending', not the generic offline copy", () => {
    const copy = getErrorCopy({ context: "zotero_push", isOffline: true });
    expect(copy.message.toLowerCase()).toContain("pending");
  });

  it("§4.3: falls back to a safe generic message with no error/offline state at all", () => {
    const copy = getErrorCopy({});
    expect(copy.title).toBeTruthy();
    expect(copy.message).toBeTruthy();
  });

  it("§5.3a: empty_results names the query that came back empty, distinct from every other context", () => {
    const copy = getErrorCopy({ context: "empty_results", query: "asdkjalksdj 12931" });
    expect(copy.title.toLowerCase()).toContain("no papers matched");
    expect(copy.message).toContain("asdkjalksdj 12931");
    // Not the generic/zotero/offline copy — this is its own distinct context.
    expect(copy.title).not.toEqual(getErrorCopy({}).title);
  });

  it("§5.3a: empty_results still falls back to the offline copy if isOffline is somehow true", () => {
    const copy = getErrorCopy({ context: "empty_results", query: "x", isOffline: true });
    expect(copy.title.toLowerCase()).toContain("offline");
  });
});
