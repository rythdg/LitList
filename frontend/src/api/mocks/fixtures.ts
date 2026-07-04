/**
 * MSW fixture data for api/ hook tests.
 *
 * These are LitList API-shaped responses (`QueueResponse`, `SavedResponse`,
 * `ZoteroCollectionsResponse`, `ZoteroPushResponse`) — not the raw PubMed/
 * Zotero payloads a real backend would call out to. Per Task 2C's scope
 * ("MSW mocks seeded from Task 0.3's fixture payloads... not invented ad
 * hoc"), the PMIDs, titles, DOI-presence, citation counts, and Zotero
 * collection/item-key values below are deliberately the *same* values as
 * `/fixtures/pubmed/esearch_response.json`, `esummary_response.json`,
 * `icite_response.json`, `zotero/collections_response.json`, and
 * `zotero/item_creation_response.json` — reshaped into the LitList
 * response envelope the frontend actually consumes, rather than invented
 * independently. See those files for the underlying source values.
 */

import type {
  QueuePaperSummary,
  QueueResponse,
  SavedResponse,
  SegmentedAbstractResponse,
  ZoteroCollectionsResponse,
  ZoteroPushResponse,
} from "../types";

// From fixtures/pubmed/esummary_response.json + efetch_response.xml +
// icite_response.json — same 3 cross-consistent PMIDs used throughout
// Task 0.3's corpus.
export const FIXTURE_PAPER_NORMAL: QueuePaperSummary = {
  pmid: "38279812",
  title: "Effects of early intervention on outcomes in a mixed-methods cohort study",
  authors: [
    { first_name: "Sofia", last_name: "Alvarez" },
    { first_name: "Wei", last_name: "Chen" },
  ],
  last_author: "Alvarez S",
  journal: "Journal of Applied Clinical Research",
  pub_date: "2024 Feb",
  doi: "10.1234/jacr.2024.001812",
  citation_count: 12,
  retracted: false,
};

// esummary_response.json's 38279813 deliberately has no DOI (§13.4);
// efetch_response.xml marks this PMID as a "Retracted Publication".
export const FIXTURE_PAPER_NO_DOI_RETRACTED: QueuePaperSummary = {
  pmid: "38279813",
  title: "A retrospective analysis of adverse events (no DOI on record)",
  authors: [{ first_name: "Li", last_name: "Chen" }],
  last_author: "Chen L",
  journal: "International Review of Medicine",
  pub_date: "2023 Nov",
  doi: null,
  citation_count: 0,
  retracted: true,
};

// icite_response.json deliberately omits 37000001 from `data` — the
// nullable-citation-count case.
export const FIXTURE_PAPER_SPARSE: QueuePaperSummary = {
  pmid: "37000001",
  title: "Older record with sparse metadata",
  authors: [],
  last_author: null,
  journal: "Legacy Medical Bulletin",
  pub_date: "1998",
  doi: null,
  citation_count: null,
  retracted: false,
};

export const FIXTURE_QUEUE_RESPONSE: QueueResponse = {
  items: [
    { paper: FIXTURE_PAPER_NORMAL, decision: "pending", position: 0 },
    { paper: FIXTURE_PAPER_NO_DOI_RETRACTED, decision: "pending", position: 1 },
    { paper: FIXTURE_PAPER_SPARSE, decision: "pending", position: 2 },
  ],
  has_more: false,
};

export const FIXTURE_EMPTY_QUEUE_RESPONSE: QueueResponse = {
  items: [],
  has_more: false,
};

export const FIXTURE_SAVED_RESPONSE: SavedResponse = {
  items: [{ paper: FIXTURE_PAPER_NORMAL, decided_at: "2026-07-01T12:00:00Z" }],
};

// Reuses the tokenizer corpus's Fig./vs. sentence and the structured
// BACKGROUND/METHODS section labels, matching CONTRACTS.md §1's own
// worked example exactly (same source sentence).
export const FIXTURE_ABSTRACT_RESPONSE: SegmentedAbstractResponse = {
  pmid: "38279812",
  narration_unavailable: false,
  segments: [
    {
      index: 0,
      kind: "section_header",
      section_label: "BACKGROUND",
      display_text: "Background",
      spoken_text: "Background.",
      char_start: 0,
      char_end: 10,
      pause_class: "structural",
    },
    {
      index: 1,
      kind: "sentence",
      section_label: "BACKGROUND",
      display_text: "Prior work has shown mixed results in Fig. 2, e.g. reduced uptake vs. controls.",
      spoken_text: "Prior work has shown mixed results in figure two, for example reduced uptake versus controls.",
      char_start: 12,
      char_end: 91,
      pause_class: "sentence",
    },
  ],
};

// From fixtures/pubmed/efetch_response.xml's non-English (Language=fre)
// record — the §13.3 language-mismatch case.
export const FIXTURE_ABSTRACT_NARRATION_UNAVAILABLE: SegmentedAbstractResponse = {
  pmid: "37000001",
  narration_unavailable: true,
  segments: [
    {
      index: 0,
      kind: "sentence",
      section_label: null,
      display_text: "Cette étude évalue les effets d'une intervention précoce.",
      spoken_text: "Cette étude évalue les effets d'une intervention précoce.",
      char_start: 0,
      char_end: 58,
      pause_class: "structural",
    },
  ],
};

// From fixtures/zotero/collections_response.json.
export const FIXTURE_ZOTERO_COLLECTIONS_RESPONSE: ZoteroCollectionsResponse = {
  connected: true,
  collections: [
    { key: "ABCD1234", name: "Journal Club" },
    { key: "WXYZ5678", name: "To Read" },
  ],
};

export const FIXTURE_ZOTERO_NOT_CONNECTED_ERROR = {
  error: {
    code: "zotero_not_connected",
    message: "Connect your Zotero account to save papers.",
  },
};

// From fixtures/zotero/item_creation_response.json: index 0 succeeds
// (key XJ2K9F3P), index 1 fails with a 503 — the partial-batch-failure
// path CONTRACTS.md §3's ZoteroPushResult shape exists to report.
export const FIXTURE_ZOTERO_PUSH_RESPONSE: ZoteroPushResponse = {
  collection_key: "ABCD1234",
  results: [
    { pmid: "38279812", status: "success", zotero_item_key: "XJ2K9F3P" },
    {
      pmid: "38279813",
      status: "failure",
      error: {
        code: "service_unavailable",
        message: "Zotero is currently unavailable. Please try again shortly.",
      },
    },
  ],
};
