/**
 * Task 4B post-review fix (adversarial-generalist "TASK 4B REVIEW",
 * finding #2): guards the Saved List panel's "Disconnect Zotero" action
 * (§5.4/§9.6) against racing an in-flight `POST /zotero/push`.
 *
 * The backend decrypts the connection's token once at request start and
 * completes the push independent of a concurrent `DELETE /zotero/
 * connection` (`backend/app/routes/zotero.py`) — so a push that's
 * already running can finish and actually write items into the user's
 * Zotero library *after* the UI has told them they're disconnected.
 * Reviewer scoped the fix to the frontend (block/confirm the racing UI
 * action) rather than backend transaction semantics, since the token is
 * already in hand by the time a concurrent disconnect could land.
 *
 * Kept as a small, independently-testable pure-ish function (the only
 * side effect is the injected `confirmFn`) rather than inlined into
 * `App.tsx`, so this guard has its own unit test without needing an
 * App-level integration test.
 */
export function confirmDisconnectDuringPush(
  isPushPending: boolean,
  confirmFn: (message: string) => boolean = (message) => window.confirm(message),
): boolean {
  if (!isPushPending) {
    return true;
  }
  return confirmFn(
    "A save to Zotero is still in progress. Disconnecting now won't stop it — it may still finish and add items to your Zotero library after you've disconnected. Disconnect anyway?",
  );
}
