import { useNetworkStore } from "./networkStore";
import { useRetryQueueStore } from "./retryQueueStore";

/**
 * Bridges the browser's real `online`/`offline` events (§4.5, §11.5) into
 * `networkStore` and, on reconnect, drains `retryQueueStore` automatically
 * (§4.5 point 4: "queued actions that make sense to retry automatically
 * ... may be retried"). Deliberately an explicit init function called
 * once from the app entry point (`main.tsx`) rather than a module-level
 * side effect, so tests can construct isolated scenarios without a global
 * `window` listener leaking across test files/suites.
 *
 * Safe to call more than once — each call attaches its own listener pair
 * and returns its own cleanup; callers that only need one long-lived
 * subscription (the real app) simply never call the returned cleanup.
 */
export function initOfflineSync(): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }

  const handleOnline = () => {
    useNetworkStore.getState().setOnline(true);
    void useRetryQueueStore.getState().retryAll();
  };

  const handleOffline = () => {
    useNetworkStore.getState().setOnline(false);
  };

  window.addEventListener("online", handleOnline);
  window.addEventListener("offline", handleOffline);

  return () => {
    window.removeEventListener("online", handleOnline);
    window.removeEventListener("offline", handleOffline);
  };
}
