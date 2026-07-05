import { describe, expect, it, vi } from "vitest";
import { confirmDisconnectDuringPush } from "./confirmDisconnectDuringPush";

describe("confirmDisconnectDuringPush (Task 4B post-review fix)", () => {
  it("allows disconnecting immediately (no confirm prompt) when no push is in flight", () => {
    const confirmFn = vi.fn(() => false);
    expect(confirmDisconnectDuringPush(false, confirmFn)).toBe(true);
    expect(confirmFn).not.toHaveBeenCalled();
  });

  it("prompts for confirmation when a push is in flight, and honors the user's answer", () => {
    const confirmYes = vi.fn(() => true);
    expect(confirmDisconnectDuringPush(true, confirmYes)).toBe(true);
    expect(confirmYes).toHaveBeenCalledWith(expect.stringMatching(/still in progress/i));

    const confirmNo = vi.fn(() => false);
    expect(confirmDisconnectDuringPush(true, confirmNo)).toBe(false);
  });
});
