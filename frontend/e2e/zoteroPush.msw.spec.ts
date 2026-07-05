import { expect, test, type Page } from "@playwright/test";
import {
  useMswInBrowser,
  useZoteroConnectedInBrowser,
  useZoteroPushMode,
} from "./support/mswBrowser";

/**
 * Playwright+MSW journeys for the Zotero push sub-flow (SPEC.md §5.5,
 * BuildPlan.md Task 4B's own cited test brief: success, connection
 * failure, push failure). Runs against the real built app (Playwright
 * config's `webServer`) with the browser-side MSW worker intercepting
 * `/api/v1/...` (`src/api/mocks/e2eHandlers.ts`) — no real backend or
 * real Zotero OAuth provider involved (that round-trip is covered by
 * the backend's own contract test, `backend/tests/test_zotero_routes.py`,
 * plus `useZoteroPushFlowController.test.tsx`'s RTL+MSW tests); these
 * specs seed the connection as already-established via
 * `useZoteroConnectedInBrowser` and exercise everything downstream of
 * that (collection choice, push success/failure, retry, disconnect).
 */
async function saveOnePaperAndOpenPushFlow(page: Page): Promise<void> {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "LitList" })).toBeVisible();
  await page.getByRole("button", { name: /swipe down to search/i }).click();

  await page.getByLabel(/search pubmed/i).fill("computational neuroscience");
  await page.getByRole("button", { name: /^start/i }).click();

  await expect(
    page.getByRole("heading", { name: /effects of early intervention/i }),
  ).toBeVisible();
  await page.getByRole("button", { name: /^interested$/i }).click();

  await page.getByRole("button", { name: /swipe up for saved list/i }).click();
  await expect(page.getByText(/saved this session \(1\)/i)).toBeVisible();

  await page.getByRole("button", { name: /push to zotero/i }).click();
}

/** Scoped to the push-flow modal, since the Saved List panel underneath
 *  it also has its own (disabled, unrelated) "Download CSV" button. */
function pushFlowDialog(page: Page) {
  return page.getByRole("dialog", { name: /save to zotero/i });
}

test.describe("Zotero push sub-flow (§5.5, Task 4B)", () => {
  test("Step 1: not-yet-connected sessions see the connect prompt", async ({ page }) => {
    await useMswInBrowser(page);
    await saveOnePaperAndOpenPushFlow(page);

    await expect(page.getByTestId("zotero-step-connect")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /connect to zotero/i }),
    ).toBeVisible();
  });

  test("Step 3a: a fully-successful push shows the success step", async ({ page }) => {
    await useMswInBrowser(page);
    await useZoteroConnectedInBrowser(page);
    await useZoteroPushMode(page, "success");
    await saveOnePaperAndOpenPushFlow(page);

    await expect(page.getByTestId("zotero-step-choose-collection")).toBeVisible();
    await page.getByLabel("Journal Club").check();
    await page.getByRole("button", { name: /^save$/i }).click();

    await expect(page.getByTestId("zotero-step-success")).toBeVisible();
    await expect(page.getByText(/saved 1 papers/i)).toBeVisible();
  });

  test("Step 3b: a per-PMID push failure (CONTRACTS.md §3) shows the failure step, distinct from a connection failure", async ({
    page,
  }) => {
    await useMswInBrowser(page);
    await useZoteroConnectedInBrowser(page);
    await useZoteroPushMode(page, "partial-failure");
    await saveOnePaperAndOpenPushFlow(page);

    await page.getByLabel("Journal Club").check();
    await page.getByRole("button", { name: /^save$/i }).click();

    const dialog = pushFlowDialog(page);
    await expect(dialog.getByTestId("zotero-step-failure")).toBeVisible();
    await expect(dialog.getByRole("button", { name: /retry/i })).toBeVisible();
    await expect(dialog.getByRole("button", { name: /download csv/i })).toBeVisible();
  });

  test("Step 3b: a connection-level push failure (the request itself failing) also reaches the failure step", async ({
    page,
  }) => {
    await useMswInBrowser(page);
    await useZoteroConnectedInBrowser(page);
    await useZoteroPushMode(page, "connection-failure");
    await saveOnePaperAndOpenPushFlow(page);

    await page.getByLabel("Journal Club").check();
    await page.getByRole("button", { name: /^save$/i }).click();

    await expect(pushFlowDialog(page).getByTestId("zotero-step-failure")).toBeVisible();
  });

  test("post-review fix (finding #1): a rapid double-click on Save fires exactly one real POST /zotero/push", async ({
    page,
  }) => {
    await useMswInBrowser(page);
    await useZoteroConnectedInBrowser(page);
    await useZoteroPushMode(page, "success");

    // Counts real network-level requests (Chrome's Network domain, which
    // Playwright's `request` event is backed by, still reports requests
    // satisfied by MSW's Service Worker) rather than a page-JS-side
    // counter — MSW's browser worker resolves handlers in a context that
    // doesn't share `window` with the page, so a handler-side counter on
    // `window` silently never gets read back.
    let pushRequestCount = 0;
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().endsWith("/zotero/push")) {
        pushRequestCount += 1;
      }
    });

    await saveOnePaperAndOpenPushFlow(page);
    await page.getByLabel("Journal Club").check();

    // Two clicks dispatched synchronously in the same task, via a single
    // `page.evaluate` — Playwright's own `.click()` re-checks
    // actionability (visible/enabled) before each click, which would
    // just wait out the button becoming disabled after the first click
    // rather than reproducing a genuine race; a real fast double-click
    // (or a stray duplicate event) fires both before React/TanStack
    // Query has had a chance to disable anything, which this reproduces
    // directly on the DOM node.
    await page.evaluate(() => {
      const button = Array.from(document.querySelectorAll("button")).find(
        (el) => el.textContent?.trim() === "Save",
      );
      button?.click();
      button?.click();
    });

    await expect(pushFlowDialog(page).getByTestId("zotero-step-success")).toBeVisible();
    expect(pushRequestCount).toBe(1);
  });
});
