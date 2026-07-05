import { setupWorker } from "msw/browser";
import { e2eHandlers } from "./e2eHandlers";

/**
 * Browser-side MSW worker (as opposed to `mocks/server.ts`'s Node
 * server, used by Vitest per Task 2C). This is *only* ever started
 * conditionally by `main.tsx`, gated on a global flag Playwright sets
 * via `page.addInitScript` before navigation (see
 * `e2e/support/mswBrowser.ts`) — production and the real-backend
 * Playwright journeys never load this module at all, so it can never
 * accidentally intercept a real request.
 *
 * Uses the *stateful* `e2eHandlers` (not Task 2C's static Vitest
 * fixtures) — a real "search -> triage -> decide -> saved list" journey
 * needs a `PATCH /decisions/{pmid}` to actually be reflected in the next
 * `GET /queue`/`GET /saved`, which a static fixture can't do.
 */
export const worker = setupWorker(...e2eHandlers);
