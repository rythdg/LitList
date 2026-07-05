import { expect, test } from "@playwright/test";
import { useMswInBrowser } from "./support/mswBrowser";

/**
 * Real drag-gesture test (SPEC.md §15.10) — Framer Motion drag doesn't
 * have a real pointer/gesture engine in jsdom (per §15.10's own note),
 * so the swipe-threshold *physical* interaction is exercised here with
 * Playwright's real mouse event emulation instead, against the actual
 * built app. The pure decision-routing/threshold-math logic itself is
 * covered in isolation by `src/gestures/useSwipeToDecide.test.ts`
 * (Vitest) — this test only proves a real drag gesture visibly produces
 * the same result as a completed swipe end to end.
 */
test.describe("drag-to-decide gesture (§5.3, §11.4, §15.10)", () => {
  test.beforeEach(async ({ page }) => {
    await useMswInBrowser(page);
    await page.goto("/");
    await page.getByRole("button", { name: /swipe down to search/i }).click();
    await page.getByLabel(/search pubmed/i).fill("computational neuroscience");
    await page.getByRole("button", { name: /^start/i }).click();
    await expect(
      page.getByRole("heading", { name: /effects of early intervention/i }),
    ).toBeVisible();
  });

  test("a rightward drag past the commit threshold marks the card Interested, same as a tap would", async ({
    page,
  }) => {
    const card = page.getByTestId("current-card");
    const box = await card.boundingBox();
    if (!box) throw new Error("current-card has no bounding box");

    const startX = box.x + box.width / 2;
    const startY = box.y + box.height / 2;

    // A real mouse-drag sequence past the 110px commit threshold —
    // Framer Motion's `drag="x"` picks this up as a genuine pointer
    // gesture, not a synthetic click.
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + 60, startY, { steps: 5 });
    await page.mouse.move(startX + 160, startY, { steps: 5 });
    await page.mouse.up();

    // The queue advances to the next paper, exactly as the tap-driven
    // happy-path journey does for the same decision.
    await expect(
      page.getByRole("heading", { name: /retrospective analysis of adverse events/i }),
    ).toBeVisible();

    await page.getByRole("button", { name: /swipe up for saved list/i }).click();
    await expect(page.getByText(/saved this session \(1\)/i)).toBeVisible();
  });

  test("a drag below the commit threshold snaps back without deciding", async ({ page }) => {
    const card = page.getByTestId("current-card");
    const box = await card.boundingBox();
    if (!box) throw new Error("current-card has no bounding box");

    const startX = box.x + box.width / 2;
    const startY = box.y + box.height / 2;

    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + 40, startY, { steps: 5 });
    await page.mouse.up();

    // Still the same paper — no decision was committed.
    await expect(
      page.getByRole("heading", { name: /effects of early intervention/i }),
    ).toBeVisible();
  });
});
