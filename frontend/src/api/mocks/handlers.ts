import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "../client";
import {
  FIXTURE_ABSTRACT_RESPONSE,
  FIXTURE_QUEUE_RESPONSE,
  FIXTURE_SAVED_RESPONSE,
  FIXTURE_ZOTERO_COLLECTIONS_RESPONSE,
  FIXTURE_ZOTERO_PUSH_RESPONSE,
} from "./fixtures";

const base = (path: string) => `${API_BASE_URL}${path}`;

/** Default "happy path" handlers, seeded from Task 0.3's fixture-derived
 * data (see mocks/fixtures.ts). Individual tests override a handler with
 * `server.use(...)` for error/edge-case paths rather than duplicating
 * this whole file per scenario. */
export const handlers = [
  http.get(base("/queue"), () => HttpResponse.json(FIXTURE_QUEUE_RESPONSE)),

  http.get(base("/papers/:pmid/abstract"), ({ params }) =>
    HttpResponse.json({ ...FIXTURE_ABSTRACT_RESPONSE, pmid: params.pmid as string }),
  ),

  http.get(base("/saved"), () => HttpResponse.json(FIXTURE_SAVED_RESPONSE)),

  http.delete(base("/saved/:pmid"), () => new HttpResponse(null, { status: 204 })),

  http.patch(base("/decisions/:pmid"), () => new HttpResponse(null, { status: 204 })),

  http.get(base("/search/settings"), () =>
    HttpResponse.json({
      query: "",
      sort: "relevance",
      read_aloud_fields: [],
      default_swipe_behavior: "not_interested",
      speed: 1,
    }),
  ),

  http.post(base("/search"), () => HttpResponse.json(FIXTURE_QUEUE_RESPONSE)),

  http.get(base("/zotero/collections"), () => HttpResponse.json(FIXTURE_ZOTERO_COLLECTIONS_RESPONSE)),

  http.post(base("/zotero/push"), () => HttpResponse.json(FIXTURE_ZOTERO_PUSH_RESPONSE)),
];
