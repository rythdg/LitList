import { expect, test } from "@playwright/test";
import { useMswInBrowser, useSearchServiceUnavailable } from "./support/mswBrowser";

/**
 * §13.6 vs. §4.5 distinctness, at the full end-to-end level (SPEC.md
 * §13.6, §15.6's final bullet): "a separate test asserting the
 * external-downtime message appears (mocked 3A `service_unavailable`
 * response) while the app correctly reports itself as online." This is
 * exactly the distinction `errorCopy.ts`'s own unit tests already cover
 * (`isOffline` always wins over any server-reported error code) and
 * that Task 4C's adversarial review confirmed correct — this spec proves
 * it also holds through the real running app, not just at the unit
 * level: `networkStore.isOnline` is never flipped by a
 * `service_unavailable` response, only by a real browser
 * `online`/`offline` event (`state/offlineSync.ts`), so a `service_
 * unavailable` response must render the §13.6 "Temporarily unavailable"
 * copy, never the §4.5 "You're offline" copy.
 */
test.describe("external dependency downtime vs. the user's own offline state (§13.6 vs §4.5)", () => {
  test("PubMed being down surfaces the external-downtime message, not the offline message, and never flips the app's own online/offline state", async ({
    page,
  }) => {
    await useMswInBrowser(page);
    await useSearchServiceUnavailable(page);

    await page.goto("/");
    await expect(page.getByRole("heading", { name: "LitList" })).toBeVisible();

    // Confirmed via the real, unmodified browser environment — this test
    // never touches `context.setOffline`/`navigator.onLine`/dispatches a
    // synthetic `offline` event at all, so if the app *did* mistakenly
    // read this condition as "you're offline," that would be a genuine
    // bug in the app, not an artifact of this test's own setup.
    expect(await page.evaluate(() => navigator.onLine)).toBe(true);

    await page.getByRole("button", { name: /swipe down to search/i }).click();
    await page.getByLabel(/search pubmed/i).fill("computational neuroscience");
    await page.getByRole("button", { name: /^start/i }).click();

    // §13.6's distinct copy (`errorCopy.ts`'s `service_unavailable`
    // branch), not §4.5's "You're offline" — `getErrorCopy` checks
    // `isOffline` *first* and would render "You're offline" instead if
    // the app had (incorrectly) inferred offline-ness from this
    // response, so asserting this exact title also proves that didn't
    // happen.
    const errorState = page.getByTestId("error-state");
    await expect(errorState).toBeVisible();
    await expect(errorState).toContainText(/temporarily unavailable/i);
    await expect(errorState).toHaveAttribute("data-code", "service_unavailable");
    await expect(page.getByText(/you're offline/i)).toHaveCount(0);
  });
});
