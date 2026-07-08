import { expect, test } from "@playwright/test";

/**
 * Live gesture test (BuildPlan.md Task 6E, SPEC.md §15.10).
 *
 * Distinct from `dragGesture.msw.spec.ts` (Task 4A): that spec runs real
 * Playwright pointer emulation against a local `vite preview` build with
 * MSW-mocked network responses. This spec runs the SAME kind of pointer
 * emulation, but against the actual deployed GitHub Pages frontend
 * talking to the actual deployed Render backend — no MSW anywhere, no
 * fixture data, real PubMed results. Run with:
 *
 *   npx playwright test --config=playwright.live.config.ts
 *
 * Traffic is deliberately kept modest (one real search, a handful of
 * decisions across three tests) so this doesn't itself trip Task 6F's
 * inbound rate limiter, which is explicitly not run concurrently with
 * this task against the same live deployment.
 */

async function startLiveSearch(page: import("@playwright/test").Page) {
  // NOTE: baseURL includes the `/LitList/` GitHub Pages sub-path, so
  // `goto("/")` (an absolute path) would resolve against the origin
  // root and hit GitHub's own 404 page, not the app — `goto("./")` (or
  // any bare relative path) correctly resolves against baseURL's own
  // path per WHATWG URL resolution rules.
  await page.goto("./");
  await page.getByRole("button", { name: /swipe down to search/i }).click();
  await page.getByLabel(/search pubmed/i).fill("cancer");
  await page.getByRole("button", { name: /^start/i }).click();
  // Real PubMed latency plus Render free-tier cold start observed to run
  // 30-50s end to end during manual verification of this task (separate
  // from any Playwright timing) — allow a generous window rather than
  // the MSW spec's near-instant expectation.
  await expect(page.getByTestId("current-card")).toBeVisible({ timeout: 60_000 });
}

test.describe("drag-to-decide gesture, live deployment (§5.3, §11.4, §15.10)", () => {
  // Independent tests, deliberately NOT serial — one test's failure
  // (e.g. live-backend flakiness) must not hide results from the
  // others in a single run.

  test("a rightward drag past the commit threshold marks the card Interested, against the real deployed app", async ({
    page,
  }) => {
    await startLiveSearch(page);

    const firstTitle = await page.locator("h2").first().innerText();

    const card = page.getByTestId("current-card");
    const box = await card.boundingBox();
    if (!box) throw new Error("current-card has no bounding box");

    const startX = box.x + box.width / 2;
    const startY = box.y + box.height / 2;

    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + 60, startY, { steps: 5 });
    await page.mouse.move(startX + 160, startY, { steps: 5 });
    await page.mouse.up();

    // The queue advances to a different paper than the one we started on.
    await expect(page.locator("h2").first()).not.toHaveText(firstTitle, { timeout: 10_000 });

    await page.getByRole("button", { name: /swipe up for saved list/i }).click();
    await expect(page.getByText(/saved this session \(1\)/i)).toBeVisible();
  });

  test("a drag below the commit threshold snaps back without deciding, against the real deployed app", async ({
    page,
  }) => {
    await startLiveSearch(page);

    const firstTitle = await page.locator("h2").first().innerText();

    const card = page.getByTestId("current-card");
    const box = await card.boundingBox();
    if (!box) throw new Error("current-card has no bounding box");

    const startX = box.x + box.width / 2;
    const startY = box.y + box.height / 2;

    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + 40, startY, { steps: 5 });
    await page.mouse.up();

    // Give any (incorrect) exit animation time to complete before
    // asserting nothing changed — a false pass here would mean the test
    // simply didn't wait long enough to see a decision commit.
    await page.waitForTimeout(500);
    await expect(page.locator("h2").first()).toHaveText(firstTitle);
  });

  test("tap/click 'Interested' and keyboard ArrowRight produce the same result as a completed swipe", async ({
    page,
  }) => {
    await startLiveSearch(page);

    const beforeTapTitle = await page.locator("h2").first().innerText();
    await page.getByRole("button", { name: "Interested", exact: true }).click();
    await expect(page.locator("h2").first()).not.toHaveText(beforeTapTitle, { timeout: 10_000 });

    const beforeKeyTitle = await page.locator("h2").first().innerText();
    // Click somewhere neutral on the card first so focus isn't sitting
    // inside a text input from the search panel, matching how a real
    // user's keyboard input would reach the document-level listener.
    await page.getByTestId("abstract-area").click();
    await page.keyboard.press("ArrowRight");
    await expect(page.locator("h2").first()).not.toHaveText(beforeKeyTitle, { timeout: 10_000 });

    // Both tap and keyboard decisions landed in the same Saved List,
    // exactly as a completed swipe-right would have (first test above).
    await page.getByRole("button", { name: /swipe up for saved list/i }).click();
    await expect(page.getByText(/saved this session \(2\)/i)).toBeVisible();
  });
});
