import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "../client";
import type { QueueItem, SegmentedAbstractResponse } from "../types";

/**
 * Stateful browser-side MSW handlers for Playwright's MSW-backed journeys
 * (`e2e/*.msw.spec.ts`) — deliberately distinct from `handlers.ts`
 * (Task 2C's static Vitest/Node fixtures). A real "search -> triage ->
 * decide -> saved list" journey (SPEC.md §4.1) needs a `PATCH
 * /decisions/{pmid}` to actually be reflected in the next `GET /queue`/
 * `GET /saved` — a static fixture response can't do that, so this module
 * keeps small in-memory state, reset automatically every page load
 * (module-level state in a fresh worker instance per Playwright
 * navigation, no explicit reset needed between tests).
 */

interface ZoteroCollectionMock {
  key: string;
  name: string;
}

interface State {
  query: string | null;
  items: QueueItem[];
  /** Task 4B addition: seeded from `e2e/support/mswBrowser.ts`'s
   *  `useZoteroConnectedInBrowser` via a `window` flag read once at
   *  module-init time (before this module's own code runs — set by
   *  Playwright's `page.addInitScript`, which always runs before any
   *  page script). Defaults `false`, matching this handler's original
   *  always-`false` behavior for every spec that never calls it. */
  zoteroConnected: boolean;
  zoteroCollections: ZoteroCollectionMock[];
}

/** Task 4B addition: which `POST /zotero/push` outcome to simulate,
 *  seeded the same way via `useZoteroPushMode`. */
type ZoteroPushMode = "success" | "partial-failure" | "connection-failure";

function readE2eWindowFlag<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  const value = (window as unknown as Record<string, unknown>)[key];
  return (value as T | undefined) ?? fallback;
}

const INITIAL_ITEMS: QueueItem[] = [
  {
    pmid: "38279812",
    position: 0,
    decision: "pending",
    title: "Effects of early intervention on outcomes in a mixed-methods cohort study",
    last_author: "Chen W",
    journal: "Journal of Applied Clinical Research",
    pub_date: "2024 Feb",
    doi: "10.1234/jacr.2024.001812",
    citation_count: 12,
    retracted: false,
  },
  {
    pmid: "38279813",
    position: 1,
    decision: "pending",
    title: "A retrospective analysis of adverse events (no DOI on record)",
    last_author: "Chen L",
    journal: "International Review of Medicine",
    pub_date: "2023 Nov",
    doi: null,
    citation_count: 0,
    retracted: true,
  },
];

const state: State = {
  query: null,
  items: INITIAL_ITEMS.map((item) => ({ ...item })),
  zoteroConnected: readE2eWindowFlag("__LITLIST_E2E_ZOTERO_CONNECTED__", false),
  zoteroCollections: [{ key: "ABCD1234", name: "Journal Club" }],
};

const zoteroPushMode: ZoteroPushMode = readE2eWindowFlag<ZoteroPushMode>(
  "__LITLIST_E2E_ZOTERO_PUSH_MODE__",
  "success",
);

function abstractFor(pmid: string): SegmentedAbstractResponse {
  return {
    pmid,
    narration_unavailable: false,
    segments: [
      {
        index: 0,
        kind: "sentence",
        section_label: null,
        display_text: "This is a short mocked abstract sentence for end-to-end testing.",
        spoken_text: "This is a short mocked abstract sentence for end to end testing.",
        char_start: 0,
        char_end: 64,
        pause_class: "structural",
      },
    ],
  };
}

const base = (path: string) => `${API_BASE_URL}${path}`;

export const e2eHandlers = [
  http.get(base("/search/settings"), () =>
    HttpResponse.json({
      query: state.query,
      sort: "relevance",
      read_aloud_fields: ["last_author", "journal", "pub_date"],
      default_swipe_behavior: "not_interested",
      speed: 1,
    }),
  ),

  http.post(base("/search"), async ({ request }) => {
    const body = (await request.json()) as { query: string };
    state.query = body.query;
    state.items = INITIAL_ITEMS.map((item) => ({ ...item }));
    return HttpResponse.json({
      items: state.items,
      total_count: state.items.length,
      has_more: false,
    });
  }),

  http.get(base("/queue"), () =>
    HttpResponse.json({
      items: state.items,
      total_count: state.items.length,
      has_more: false,
    }),
  ),

  http.get(base("/papers/:pmid/abstract"), ({ params }) =>
    HttpResponse.json(abstractFor(params.pmid as string)),
  ),

  http.patch(base("/decisions/:pmid"), async ({ params, request }) => {
    const body = (await request.json()) as { decision: QueueItem["decision"] };
    const item = state.items.find((i) => i.pmid === params.pmid);
    if (item) item.decision = body.decision;
    return new HttpResponse(null, { status: 204 });
  }),

  http.get(base("/saved"), () =>
    HttpResponse.json({
      items: state.items
        .filter((item) => item.decision === "interested")
        .map(({ pmid, title, last_author, journal, pub_date, doi, citation_count, position, retracted }) => ({
          pmid,
          title,
          last_author,
          journal,
          pub_date,
          doi,
          citation_count,
          position,
          retracted,
        })),
    }),
  ),

  http.delete(base("/saved/:pmid"), ({ params }) => {
    const item = state.items.find((i) => i.pmid === params.pmid);
    if (item) item.decision = "not_interested";
    return new HttpResponse(null, { status: 204 });
  }),

  http.get(base("/zotero/collections"), () => {
    if (!state.zoteroConnected) {
      return HttpResponse.json(
        {
          error: {
            code: "zotero_not_connected",
            message: "Connect your Zotero account to save papers.",
          },
        },
        { status: 401 },
      );
    }
    return HttpResponse.json({ connected: true, collections: state.zoteroCollections });
  }),

  // Task 4B additions below (§8.5-§8.7/§9.6, CONTRACTS.md §3/§4) — the
  // OAuth handshake itself has no MSW-mockable equivalent (real browser
  // navigation through a real Zotero provider), so `zoteroConnected`
  // starts pre-seeded via `useZoteroConnectedInBrowser` rather than being
  // flipped by an in-journey "Connect to Zotero" click.
  http.post(base("/zotero/collections"), async ({ request }) => {
    const body = (await request.json()) as { name: string };
    const collection: ZoteroCollectionMock = {
      key: `NEW-${state.zoteroCollections.length + 1}`,
      name: body.name,
    };
    state.zoteroCollections.push(collection);
    return HttpResponse.json({ collection });
  }),

  http.post(base("/zotero/push"), async ({ request }) => {
    if (zoteroPushMode === "connection-failure") {
      return HttpResponse.json(
        {
          error: {
            code: "service_unavailable",
            message: "Zotero is currently unavailable. Please try again shortly.",
          },
        },
        { status: 503 },
      );
    }
    const body = (await request.json()) as { collection_key: string; pmids: string[] };
    const results = body.pmids.map((pmid, index) =>
      zoteroPushMode === "partial-failure" && index === 0
        ? {
            pmid,
            status: "failure" as const,
            error: {
              code: "service_unavailable",
              message: "Zotero is currently unavailable. Please try again shortly.",
            },
          }
        : { pmid, status: "success" as const, zotero_item_key: `KEY-${pmid}` },
    );
    return HttpResponse.json({ collection_key: body.collection_key, results });
  }),

  http.delete(base("/zotero/connection"), () => {
    state.zoteroConnected = false;
    return new HttpResponse(null, { status: 204 });
  }),
];
