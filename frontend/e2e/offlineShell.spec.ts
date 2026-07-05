import { expect, test } from "@playwright/test";

/**
 * PWA shell offline load (SPEC.md §11.5, §15.6's first bullet: "App
 * shell (cached via the service worker, §11.5) still loads with no
 * network"). Deliberately does *not* use `useMswInBrowser` — this test
 * is about `vite-plugin-pwa`'s real generated `sw.js` precaching the app
 * shell (JS/CSS/HTML/icons only, per §11.5 — never PubMed/paper data),
 * not about the API mock layer, so it exercises the real production
 * service worker from the real built `dist/` (Playwright config's
 * `webServer`).
 *
 * Uses Playwright's real `context.setOffline(true)` (CDP-level network
 * blocking) rather than the `dispatchConnectivityEvent`/handler-flag
 * approach the MSW-backed offline specs use — there is no MSW Service
 * Worker registered here to make that distinction matter, so real
 * network blocking is both correct and the more realistic test for
 * "does the actual precache work."
 */
test.describe("PWA shell offline load (§11.5, §15.6)", () => {
  test("the precached app shell still loads with no network on reload", async ({ page, context }) => {
    // First load online so the service worker installs, activates, and
    // precaches the shell.
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "LitList" })).toBeVisible();

    // `vite-plugin-pwa`'s `registerType: 'autoUpdate'` (Task 2A,
    // vite.config.ts) enables workbox's `skipWaiting`/`clientsClaim`, so
    // the very first installed worker takes control without requiring an
    // extra manual reload first — `navigator.serviceWorker.ready`
    // resolves once that activation/control has happened.
    await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller), null, {
      timeout: 15_000,
    });

    await context.setOffline(true);
    await page.reload();

    // The shell (heading, static markup) loads from the precache with no
    // network at all — a real offline browser would show a
    // connection-error interstitial instead if this weren't cached.
    await expect(page.getByRole("heading", { name: "LitList" })).toBeVisible();

    await context.setOffline(false);
  });
});
