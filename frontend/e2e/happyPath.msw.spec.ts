import { expect, test } from "@playwright/test";
import { useMswInBrowser } from "./support/mswBrowser";

/**
 * Playwright+MSW happy-path journey (SPEC.md §4.1, §15.3, §15.10):
 * search -> triage (decide on the current card) -> saved list. Runs
 * against the real built app (Playwright config's `webServer`) with the
 * browser-side MSW worker intercepting `/api/v1/...` (see
 * `src/api/mocks/e2eHandlers.ts`) — no real backend involved, but a real
 * browser, a real DOM, and the app's real production bundle.
 */
test.describe("happy-path journey (§4.1)", () => {
  test.beforeEach(async ({ page }) => {
    await useMswInBrowser(page);
  });

  test("search, decide on the current card via tap, then find it in the saved list", async ({ page }) => {
    await page.goto("/");

    // Screen A (Idle) — no search has run yet.
    await expect(page.getByRole("heading", { name: "LitList" })).toBeVisible();
    await page.getByRole("button", { name: /swipe down to search/i }).click();

    // Screen B (Search & Settings).
    await page.getByLabel(/search pubmed/i).fill("computational neuroscience");
    await page.getByRole("button", { name: /^start/i }).click();

    // Screen C (Stack) — the first queued paper is now current.
    await expect(
      page.getByRole("heading", { name: /effects of early intervention/i }),
    ).toBeVisible();

    // Decide via tap (§11.4 — one of the three equivalent input paths).
    await page.getByRole("button", { name: /^interested$/i }).click();

    // The queue advances to the next paper (the decided-on one is no
    // longer current).
    await expect(
      page.getByRole("heading", { name: /retrospective analysis of adverse events/i }),
    ).toBeVisible();

    // Saved List (Screen D) now contains the paper marked Interested.
    await page.getByRole("button", { name: /swipe up for saved list/i }).click();
    await expect(page.getByText(/saved this session \(1\)/i)).toBeVisible();
    await expect(
      page.getByText(/effects of early intervention/i),
    ).toBeVisible();
  });
});
