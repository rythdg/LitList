/**
 * Fixed URL-based route paths (§11.6).
 *
 * LitList's IA (Section 3) is one screen with panels toggled by gesture/
 * UI state (§3.3) — not a set of distinct pages — so no general-purpose
 * router is introduced. The Zotero OAuth callback is the **one**
 * exception: Zotero genuinely needs a real, fixed URL to redirect the
 * user's browser back to (§8.2 steps 3-4).
 */

/**
 * Where the backend's OAuth callback (`GET /api/v1/zotero/auth/callback`,
 * Task 3B) redirects the browser after completing the token exchange.
 * Must remain a fixed, non-attacker-influenceable path — §8.2 calls out
 * that accepting a dynamic redirect target here would be an open-redirect
 * vector, so this is a hardcoded constant, never derived from a query
 * parameter.
 */
export const ZOTERO_OAUTH_CALLBACK_PATH = '/oauth/zotero/callback';

/** The single-page app's home path — everything that isn't the OAuth
 *  callback route above lives here, gated by in-app panel state instead
 *  of the URL. */
export const HOME_PATH = '/';
