import { defineConfig, devices } from "@playwright/test";

/**
 * Live-infra Playwright config (BuildPlan.md Task 6A, SPEC.md §15.4).
 *
 * Separate from `playwright.config.ts` on purpose: that file's specs are
 * all MSW-mocked (`useMswInBrowser` flips a `window` flag the *locally
 * built* app checks before deciding whether to hit a mock worker or a
 * real backend) or depend on a `vite preview` server Playwright starts
 * itself — neither applies to the real deployed frontend, which is a
 * static GitHub Pages build with no local server and no MSW flag wired
 * for a stranger's browser session. Rather than retrofit every existing
 * MSW spec to somehow also run "live" (they can't — there is no local
 * backend to point at, and the real backend's data/session state isn't
 * MSW's fixed fixture corpus), this config runs a small, separate
 * `e2e-live/` smoke suite directly against:
 *   - frontend: https://rythdg.github.io/LitList/ (real GitHub Pages)
 *   - backend:  https://litlist-backend.onrender.com (real Render/Turso)
 * across the same three engines §15.4 asks for. No `webServer` block —
 * there is nothing local to start; this hits the internet.
 */
export default defineConfig({
  testDir: "./e2e-live",
  fullyParallel: false,
  // Live smoke tests share real backend session/DB state and hit a real
  // rate-limited external API (PubMed) — sequential run avoids the kind
  // of cross-test interference BuildPlan.md's Tier 6 note (6F vs.
  // 6A/6E) already flags for this exact deployment.
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [["list"]],
  // Generous relative to `playwright.config.ts`'s local/MSW suite: the
  // real backend's own health-poll warm-up (in `liveSmoke.spec.ts`'s
  // `beforeEach`, up to 90s on a cold Render free-tier instance) plus
  // the actual UI journey both count against this same per-test budget.
  timeout: 240_000,
  use: {
    baseURL: "https://rythdg.github.io/LitList/",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
    },
  ],
});
