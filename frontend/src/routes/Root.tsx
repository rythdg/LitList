/**
 * Minimal manual routing (§11.6).
 *
 * LitList's IA (Section 3) is fundamentally one screen with panels
 * toggled by gesture/UI state (§3.3), not a set of distinct pages — so a
 * full router (React Router or similar) is deliberately not introduced,
 * per §11.6. The **one** exception is the Zotero OAuth callback, which
 * needs a real URL for Zotero to redirect back to (§8.2 steps 3-4);
 * that's handled here as a single pathname check rather than justifying
 * a router dependency for the whole app.
 */
import { useEffect, useState } from 'react';
import App from '../App';
import { ZoteroCallbackRoute } from './ZoteroCallbackRoute';
import { ZOTERO_OAUTH_CALLBACK_PATH } from './paths';

export function Root() {
  const [pathname, setPathname] = useState(
    () => window.location.pathname,
  );

  useEffect(() => {
    const onPopState = () => setPathname(window.location.pathname);
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  if (pathname === ZOTERO_OAUTH_CALLBACK_PATH) {
    return <ZoteroCallbackRoute />;
  }

  return <App />;
}
