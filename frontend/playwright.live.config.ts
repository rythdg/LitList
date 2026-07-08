import { defineConfig, devices } from "@playwright/test";

/**
 * Live-target Playwright config (BuildPlan.md Task 6E, SPEC.md §15.10).
 *
 * Unlike `playwright.config.ts` (Task 4A), this config does NOT start a
 * local `vite preview` server and does NOT point at localhost — it runs
 * against the actual deployed GitHub Pages frontend, which in turn talks
 * to the actual deployed Render backend (baked in at build time via
 * `VITE_API_BASE_URL`). No MSW is used by specs run under this config;
 * `frontend/e2e/*.live.spec.ts` files exercise the real, un-mocked
 * network path end to end.
 *
 * Deliberately single-worker, no retries, low volume: Task 6E must not
 * generate enough traffic to trip Task 6F's inbound rate-limiter tests
 * (which are explicitly sequenced not to run concurrently with 6A/6E
 * against the same live deployment).
 */
export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*\.live\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [["list"]],
  timeout: 90_000,
  use: {
    baseURL: "https://rythdg.github.io/LitList/",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
