import { expect, test } from "@playwright/test";

const BACKEND_HEALTH_URL = "https://litlist-backend.onrender.com/health";

/**
 * Waits for the real deployed backend to be responsive before driving
 * the UI. Task 6A discovery (verbatim, not a guess): the real backend on
 * Render's free tier spins down after inactivity and, while restarting,
 * intermittently returns `502` (Render's own gateway error page, not
 * this app's) for anywhere from several seconds up to roughly half a
 * minute, including flapping between `502` and `200` mid-restart before
 * settling. This is a real, observed characteristic of the current free-
 * tier hosting (BuildPlan.md Task 5A territory, not a frontend bug) —
 * without this warm-up, a live smoke test run against a cold instance
 * fails identically on all three engines for a reason that has nothing
 * to do with cross-browser compatibility, which would misreport an
 * infra/hosting fact as a Task 6A finding.
 */
async function waitForBackendWarm(maxWaitMs = 120_000): Promise<void> {
  const deadline = Date.now() + maxWaitMs;
  let lastStatus: number | string = "never tried";
  // Task 6A discovery (verbatim): a single `200` isn't reliable evidence
  // the instance is actually warm — mid-restart, the free-tier instance
  // observably flaps between `502` and `200` before settling. Requiring
  // 3 consecutive successes (spaced out) avoids kicking off the real UI
  // journey during exactly that flapping window, which would otherwise
  // fail the in-flight `POST /search` moments later for the same reason.
  let consecutiveOk = 0;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(BACKEND_HEALTH_URL);
      lastStatus = res.status;
      consecutiveOk = res.ok ? consecutiveOk + 1 : 0;
      if (consecutiveOk >= 3) return;
    } catch (err) {
      lastStatus = (err as Error).message;
      consecutiveOk = 0;
    }
    await new Promise((r) => setTimeout(r, 3_000));
  }
  throw new Error(
    `Real backend at ${BACKEND_HEALTH_URL} never became stably healthy within ${maxWaitMs}ms (last status: ${lastStatus}). This is a live-infra availability problem, not a frontend/cross-browser issue.`,
  );
}

/**
 * Live cross-browser smoke test (BuildPlan.md Task 6A, SPEC.md §15.4).
 *
 * Runs against the REAL deployed frontend (GitHub Pages,
 * `playwright.live.config.ts`'s `baseURL`) talking to the REAL deployed
 * backend (Render + Turso) — no MSW, no mocks, real PubMed data behind
 * `POST /api/v1/search`. This is deliberately a thin happy-path subset,
 * not the full regression suite: the point of Task 6A is proving the
 * real production bundle behaves the same across Chromium, Firefox, and
 * WebKit when talking to real infra, not re-litigating every scenario
 * the local MSW suite (`e2e/*.msw.spec.ts`) already covers against a
 * fixed fixture corpus.
 *
 * Because this hits a real, live-changing PubMed corpus, assertions are
 * deliberately shape-based (a heading exists, its text is non-empty,
 * counts move) rather than pinned to specific paper titles the way the
 * MSW-backed specs can afford to be.
 */
test.describe("live smoke — real frontend + real backend (§15.4)", () => {
  test.beforeEach(async () => {
    await waitForBackendWarm();
  });

  test("search returns a real queue, deciding on the current card advances it, and it lands in the saved list", async ({
    page,
  }) => {
    await page.goto("./");

    // Screen A (Idle). A dismissible cookie notice (§10.2/§11.7) may be
    // present on first visit — dismiss it if so, same as a real user
    // would, before interacting with anything below it.
    await expect(page.getByRole("heading", { name: "LitList" })).toBeVisible();
    const cookieDismiss = page.getByRole("button", { name: /dismiss cookie notice/i });
    if (await cookieDismiss.count()) {
      await cookieDismiss.click();
    }
    await page.getByRole("button", { name: /swipe down to search/i }).click();

    // Screen B (Search & Settings) — a specific, moderately-scoped query
    // against the real PubMed corpus via the real backend. Deliberately
    // not an extremely broad single word (e.g. "cancer") — Task 6A
    // discovered such queries can push the real backend's PubMed
    // round-trip past Render's own gateway timeout, producing a 502
    // that has nothing to do with cross-browser behavior.
    await page.getByLabel(/search pubmed/i).fill("computational neuroscience");
    await page.getByRole("button", { name: /^start/i }).click();

    // Screen C (Stack) — real search can be slow (real PubMed round
    // trip through the real backend), so this waits generously rather
    // than assuming MSW's instant mock response time.
    const currentCardHeading = page.getByTestId("current-card").getByRole("heading", { level: 2 });
    // Task 6A discovery (verbatim): a real `POST /search` round trip
    // against the real backend was independently observed (via direct
    // `curl`, outside any browser/Playwright involvement) taking
    // 30-34s even while the instance reports itself healthy — plausibly
    // near Render's own gateway timeout, which would also explain the
    // intermittent `502`s seen on this same endpoint outside any
    // maintenance/cold-start window. 60s gives headroom above that
    // observed real latency without papering over a hang.
    await expect(currentCardHeading).toBeVisible({ timeout: 60_000 });
    const firstTitle = (await currentCardHeading.textContent())?.trim() ?? "";
    expect(firstTitle.length).toBeGreaterThan(0);

    // Decide via tap (§11.4) — one of the three equivalent input paths;
    // the other two (swipe, keyboard) are exercised against real
    // pointer/keyboard events by the local MSW-backed
    // `dragGesture.msw.spec.ts` and by Task 6E's live gesture pass, so
    // this live smoke test only needs to prove the tap path works
    // end-to-end against real infra, not re-cover every modality here.
    await page.getByRole("button", { name: /^interested$/i }).click();

    // The queue advances: the heading text changes to a different real
    // paper (or, in the rare case the corpus has exactly one matching
    // result, the empty-queue state is shown instead — either is a
    // valid "advanced" outcome against live data).
    await expect
      .poll(
        async () =>
          (await currentCardHeading.count()) === 0 || (await currentCardHeading.textContent())?.trim() !== firstTitle,
        { timeout: 15_000 },
      )
      .toBe(true);

    // Saved List (Screen D) now contains at least the one decided-on
    // paper. Asserts a count of *at least 1* specifically (not just "a
    // digit," which `\d+` would also match on the empty-list `(0)`
    // state a Task 6A run once let slip through) and that the decided
    // paper's own title text is present verbatim.
    await page.getByRole("button", { name: /swipe up for saved list/i }).click();
    await expect(page.getByRole("heading", { name: /saved this session \([1-9]\d*\)/i })).toBeVisible({
      timeout: 15_000,
    });
    const escapedTitleFragment = firstTitle.slice(0, 20).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    await expect(page.getByText(new RegExp(escapedTitleFragment, "i"))).toBeVisible();
  });
});
