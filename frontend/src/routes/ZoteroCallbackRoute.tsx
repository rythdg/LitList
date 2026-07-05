/**
 * Zotero OAuth callback screen shell (§8.2 steps 3-4, §11.6).
 *
 * This is the one real URL-based route in LitList (§11.6): Zotero
 * redirects the user's browser here after the backend
 * (`GET /api/v1/zotero/auth/callback`, Task 3B) has already completed
 * the OAuth token exchange server-side and stored the `ZoteroConnection`.
 * LitList never sees a Zotero token/secret in the browser (no client-side
 * secrets, ever) — this component only reads a small status signal the
 * backend's redirect is expected to attach as query params, then hands
 * off back into the single-page app.
 *
 * Per BuildPlan.md's scope for Task 2A, this is a **route/screen shell
 * only** — the real OAuth wiring (Task 3B's backend redirect target
 * details, and Tier 4's hookup of "success" into Screen D1 Step 2
 * collection selection, §5.5) is out of scope here.
 *
 * Query-param shape confirmed against the real backend redirect and
 * pinned in CONTRACTS.md §6 by Task 4B — this component's own parsing
 * (`zoteroCallbackParams.ts`) needed no change, since 2A's original
 * assumption (`?status=success` / `?status=error&code=...&message=...`,
 * reusing CONTRACTS.md #2's `ApiError` `code`/`message` fields) turned
 * out to be the shape the backend needed to be fixed to match, not the
 * other way around — see CONTRACTS.md §6's own note and this repo's
 * senior-fullstack-developer build log, "TASK 4B — PIVOT".
 *
 * On success, this also writes a one-shot `sessionStorage` flag
 * (`zoteroPushFlowStore.ts`'s `ZOTERO_REOPEN_FLAG_KEY`) before handing
 * off back into the SPA — since this route is reached via a real, hard
 * page navigation (every in-memory store starts fresh here), that flag
 * is how the Saved List panel's push-flow modal knows to reopen itself
 * once the app remounts, without SPEC.md requiring a separate "login
 * success" screen (§8.2 step 6: "the app proceeds straight to collection
 * selection").
 */
import { useEffect, useState } from 'react';
import { HOME_PATH } from './paths';
import { parseCallbackParams, type ParsedCallback } from './zoteroCallbackParams';
import { ZOTERO_REOPEN_FLAG_KEY } from '../state/zoteroPushFlowStore';

/**
 * Navigates back into the single-page app without a full page reload.
 * Real hand-off into Screen D1 Step 2 (collection selection) on success
 * is Tier 4's job, once Task 2C's Zustand "active panel" store exists —
 * this only proves the route/redirect mechanics work end to end.
 */
function goHome() {
  window.history.replaceState({}, '', HOME_PATH);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

export function ZoteroCallbackRoute() {
  const [result] = useState<ParsedCallback>(() =>
    parseCallbackParams(window.location.search),
  );

  useEffect(() => {
    if (result.status === 'success' && typeof sessionStorage !== 'undefined') {
      sessionStorage.setItem(ZOTERO_REOPEN_FLAG_KEY, '1');
    }
  }, [result.status]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-white px-6 text-center text-slate-900">
      {result.status === 'success' && (
        <>
          <h1 className="text-xl font-semibold">Connected to Zotero</h1>
          <p className="text-sm text-slate-600">
            Your Zotero account is now connected. Choose a collection to
            continue.
          </p>
        </>
      )}
      {result.status === 'error' && (
        <>
          <h1 className="text-xl font-semibold">
            Couldn&rsquo;t connect to Zotero
          </h1>
          {/* result.message is rendered as plain React text content only
              — never via dangerouslySetInnerHTML — matching §6.5/§11.3's
              no-raw-HTML rule, even though this particular string is
              expected to be LitList's own pre-written copy, not PubMed
              data. */}
          <p className="text-sm text-slate-600">
            {result.message ??
              "Something went wrong connecting your Zotero account. Please try again."}
          </p>
        </>
      )}
      {result.status === 'unknown' && (
        <>
          <h1 className="text-xl font-semibold">Connecting to Zotero&hellip;</h1>
          <p className="text-sm text-slate-600">
            If this message doesn&rsquo;t go away, return to LitList and try
            connecting again.
          </p>
        </>
      )}
      <button
        type="button"
        onClick={goHome}
        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
      >
        Continue to LitList
      </button>
    </main>
  );
}
