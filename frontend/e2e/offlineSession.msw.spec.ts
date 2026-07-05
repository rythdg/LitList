import { expect, test } from "@playwright/test";
import {
  dispatchConnectivityEvent,
  setDecisionNetworkDown,
  setDecisionNotFound,
  useMswInBrowser,
} from "./support/mswBrowser";

/**
 * Playwright+MSW offline-mid-session journeys (SPEC.md §4.5, §15.6's
 * 2nd/3rd bullets): "a swipe session already in progress doesn't crash
 * when connectivity drops mid-session" and "queued actions... retried on
 * reconnect." Deferred from Task 4C (BuildPlan.md lines 632-646) until
 * `App.tsx`/the Playwright harness existed; both now do.
 *
 * See `e2e/support/mswBrowser.ts`'s `setDecisionNetworkDown`/
 * `dispatchConnectivityEvent` docstrings for why these specs don't use
 * `context.setOffline` the way `offlineShell.spec.ts` does: MSW's
 * Service-Worker-based interception never touches the real network, so
 * Chromium's offline emulation has no effect on it. `setDecisionNetworkDown`
 * makes the mocked `PATCH /decisions/{pmid}` fail the way a real offline
 * `fetch()` would; `dispatchConnectivityEvent` fires the same real
 * `window` `online`/`offline` events `state/offlineSync.ts`'s real
 * listener (wired from `main.tsx`) reacts to — so the actual production
 * `networkStore`/`offlineSync`/`retryQueueStore` machinery is what's
 * under test here, not a stand-in for it.
 */
async function startSessionAndReachStack(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "LitList" })).toBeVisible();
  await page.getByRole("button", { name: /swipe down to search/i }).click();

  await page.getByLabel(/search pubmed/i).fill("computational neuroscience");
  await page.getByRole("button", { name: /^start/i }).click();

  await expect(
    page.getByRole("heading", { name: /effects of early intervention/i }),
  ).toBeVisible();
}

test.describe("offline mid-session (§4.5, §15.6)", () => {
  test.beforeEach(async ({ page }) => {
    await useMswInBrowser(page);
  });

  test("a decision made mid-session after connectivity drops doesn't crash the app and still advances the queue locally", async ({
    page,
  }) => {
    const pageErrors: Error[] = [];
    page.on("pageerror", (error) => pageErrors.push(error));

    await startSessionAndReachStack(page);

    // The user's own connection drops (§4.5 point 1) — the real
    // `offlineSync.ts` listener flips `networkStore.isOnline` to `false`
    // off this exact event, and the mocked decision endpoint is made to
    // fail the way a real offline `fetch()` would.
    await dispatchConnectivityEvent(page, "offline");
    await setDecisionNetworkDown(page, true);

    // Decide via tap while offline — §11.4's single decision function
    // still runs synchronously (optimistic update, §11.2) regardless of
    // whether the network call behind it will succeed.
    await page.getByRole("button", { name: /^interested$/i }).click();

    // §4.5 point 2: papers already loaded keep working — the queue
    // advances to the next paper immediately, offline or not, and
    // nothing crashes.
    await expect(
      page.getByRole("heading", { name: /retrospective analysis of adverse events/i }),
    ).toBeVisible();

    expect(pageErrors).toEqual([]);
  });

  test("a decision queued while offline is retried and actually reaches the server once the app reconnects", async ({
    page,
  }) => {
    // Not verified via Playwright's `request`/`requestfailed` events:
    // MSW's `HttpResponse.error()` (the network-error simulation) never
    // generates a CDP "Network.requestWillBeSent" event at all in this
    // MSW/Chromium combination — confirmed empirically (a `page.on(...)`
    // listener across every request-lifecycle event sees nothing for the
    // errored PATCH, while the same listener sees every other
    // MSW-mocked GET/POST in this same journey normally). So this test
    // verifies the real, user-visible consequence instead: the Saved
    // List reflects `GET /saved`'s *actual server-side* state (Task 4B's
    // in-memory `e2eHandlers.ts` store), not the client's optimistic
    // queue cache — if the queued decision were silently dropped instead
    // of retried, this would still read "(0)" forever after reconnect.
    await startSessionAndReachStack(page);

    await dispatchConnectivityEvent(page, "offline");
    await setDecisionNetworkDown(page, true);

    await page.getByRole("button", { name: /^interested$/i }).click();
    await expect(
      page.getByRole("heading", { name: /retrospective analysis of adverse events/i }),
    ).toBeVisible();

    // Server-side, the decision never actually landed (the request
    // failed before reaching `e2eHandlers.ts`'s in-memory store) — the
    // Saved List, which reflects the real `GET /saved` response rather
    // than the optimistic local queue state, still shows nothing.
    await page.getByRole("button", { name: /swipe up for saved list/i }).click();
    await expect(page.getByText(/saved this session \(0\)/i)).toBeVisible();
    await page.getByRole("button", { name: /swipe down to collapse/i }).click();

    // Reconnect (§4.5 point 4): the decision endpoint starts succeeding
    // again, and the real `online` event fires `offlineSync.ts`'s
    // `retryQueueStore.retryAll()` automatically — no manual retry
    // affordance clicked here, this is the *automatic* retry-on-reconnect
    // path; nothing else happens between this line and the assertion
    // below that could otherwise explain the Saved List changing.
    await setDecisionNetworkDown(page, false);
    await dispatchConnectivityEvent(page, "online");

    // The retried PATCH actually reaches the (still-mocked, but now
    // succeeding) server this time, and the Saved List — driven by the
    // real `GET /saved` response, not a client-only fiction — now
    // reflects it.
    await page.getByRole("button", { name: /swipe up for saved list/i }).click();
    await expect(page.getByText(/saved this session \(1\)/i)).toBeVisible();
    await expect(page.getByText(/effects of early intervention/i)).toBeVisible();
  });

  test("adversarial review Finding 2: a decision queued while offline shows a visible pending indicator, which clears once the retry actually succeeds", async ({
    page,
  }) => {
    await startSessionAndReachStack(page);

    await dispatchConnectivityEvent(page, "offline");
    await setDecisionNetworkDown(page, true);
    await page.getByRole("button", { name: /^interested$/i }).click();

    // Before this fix, a queued-but-unsaved decision was indistinguishable
    // from a saved one anywhere in the UI — `PendingRetryBanner` is the
    // real, user-visible signal that it hasn't actually saved yet.
    const banner = page.getByTestId("pending-retry-banner");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText(/1 change is pending/i);
    await expect(banner).toContainText(/will retry when back online/i);

    await setDecisionNetworkDown(page, false);
    await dispatchConnectivityEvent(page, "online");

    // Once the automatic retry actually succeeds, the banner clears —
    // it reflects `retryQueueStore`'s real, live contents, not a
    // one-shot message that would otherwise linger forever.
    await expect(banner).not.toBeVisible();
  });

  test("adversarial review Finding 1: a decision that fails again for a real reason on retry (not another network drop) stops retrying and surfaces as a failure, not an invisible infinite loop", async ({
    page,
  }) => {
    await startSessionAndReachStack(page);

    await dispatchConnectivityEvent(page, "offline");
    await setDecisionNetworkDown(page, true);
    await page.getByRole("button", { name: /^interested$/i }).click();
    await expect(page.getByTestId("pending-retry-banner")).toBeVisible();

    // Reconnect, but something genuinely changed server-side while this
    // sat queued (session expired, the paper no longer exists, etc.) —
    // the retried request now gets a real `not_found` `ApiError`, not
    // another network drop.
    await setDecisionNetworkDown(page, false);
    await setDecisionNotFound(page, true);
    await dispatchConnectivityEvent(page, "online");

    // Not stuck in an invisible infinite retry loop...
    await expect(page.getByTestId("pending-retry-banner")).not.toBeVisible();
    // ...surfaced as a real, visible failure instead.
    const failed = page.getByTestId("failed-retry-item");
    await expect(failed).toBeVisible();
    await expect(failed).toContainText(/couldn.t save/i);
    await expect(failed).toContainText(/decision not found/i);

    // A later reconnect doesn't resurrect it into the pending queue —
    // it stays a dismissed-by-the-user concern from here.
    await dispatchConnectivityEvent(page, "offline");
    await dispatchConnectivityEvent(page, "online");
    await expect(page.getByTestId("pending-retry-banner")).not.toBeVisible();
    await expect(failed).toBeVisible();

    await failed.getByRole("button", { name: /dismiss/i }).click();
    await expect(failed).not.toBeVisible();
  });
});
