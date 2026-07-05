import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config (BuildPlan.md Task 4A, SPEC.md §15.10).
 *
 * Runs against `vite preview` (a real production-ish build served
 * statically) rather than `vite dev`, so these tests exercise the same
 * bundle the app actually ships, including the PWA service worker
 * registration path — consistent with §15.5's Lighthouse pass also
 * running against `dist/`. Playwright starts/stops this server itself.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:4173",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    // Assumes `npm run build` has already produced `dist/` (the test
    // script below runs it explicitly first) — chaining the build into
    // this command was flaky under Playwright's own process/port-ready
    // detection, since the build's own stdout briefly looks like a
    // ready server to a naive "did it start" check.
    //
    // `vite preview` with no `--host` binds IPv6 `localhost`
    // (`::1`) only, not `127.0.0.1` — Playwright's readiness probe
    // against a literal `127.0.0.1` URL would otherwise time out and
    // kill an otherwise-healthy server, so both `baseURL` above and this
    // `url` use `localhost`, matching what the server actually binds.
    command: "npm run preview -- --port 4173 --strictPort",
    url: "http://localhost:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
