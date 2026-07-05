/**
 * Hand-written fixture data for Task 2B's presentational screens.
 *
 * Cross-referencing the same PMIDs as fixtures/pubmed/*.json (Task 0.3)
 * so this corpus lines up with what the rest of the project uses for the
 * same edge cases: 38279812 (normal), 38279813 (retracted, no DOI),
 * 37000001 (non-English / narration-unavailable).
 *
 * Reshaped to the flat CONTRACTS.md §5 shape during Task 4A (no nested
 * `paper`/`authors[]`, `last_author` is a plain display string,
 * `retracted` is a boolean) — see this file's history/CONTRACTS.md's
 * change log for why.
 */
import type { AbstractSegment, QueueItem, SearchSettings } from "./types";

export const paperNormal: QueueItem = {
  pmid: "38279812",
  position: 0,
  decision: "pending",
  title:
    "Effects of early intervention on outcomes in a mixed-methods cohort study",
  last_author: "Chen W",
  journal: "Journal of Applied Clinical Research",
  pub_date: "2024 Feb",
  doi: "10.1234/jacr.2024.001812",
  citation_count: 12,
  retracted: false,
};

export const paperNextUp: QueueItem = {
  pmid: "37000001",
  position: 1,
  decision: "pending",
  title: "Temporal Coding in Cortical Microcircuits During Active Sensing",
  last_author: null,
  journal: "Legacy Medical Bulletin",
  pub_date: "1998",
  doi: null,
  citation_count: null,
  retracted: false,
};

export const paperRetracted: QueueItem = {
  pmid: "38279813",
  position: 2,
  decision: "pending",
  title: "A retrospective analysis of adverse events (no DOI on record)",
  last_author: "Chen L",
  journal: "International Review of Medicine",
  pub_date: "2023 Nov",
  doi: null,
  citation_count: 3,
  retracted: true,
};

export const mockQueue: QueueItem[] = [paperNormal, paperNextUp, paperRetracted];

export const mockSavedItems: QueueItem[] = [
  { ...paperNormal, decision: "interested" },
  { ...paperNextUp, decision: "interested" },
];

/** Matches CONTRACTS.md §1's `AbstractSegment` shape for `paperNormal`. */
export const mockSegments: AbstractSegment[] = [
  {
    index: 0,
    kind: "sentence",
    section_label: null,
    display_text: "Results are shown in Fig. 2.",
    spoken_text: "Results are shown in figure two.",
    char_start: 0,
    char_end: 29,
    pause_class: "structural",
  },
  {
    index: 1,
    kind: "sentence",
    section_label: null,
    display_text:
      "Sample sizes varied widely across the six included cohorts.",
    spoken_text: "Sample sizes varied widely across the six included cohorts.",
    char_start: 30,
    char_end: 91,
    pause_class: "sentence",
  },
  {
    index: 2,
    kind: "sentence",
    section_label: null,
    display_text:
      "As shown by Smith et al. in a prior cohort, early intervention improved outcomes.",
    spoken_text:
      "As shown by Smith et al. in a prior cohort, early intervention improved outcomes.",
    char_start: 92,
    char_end: 175,
    pause_class: "sentence",
  },
];

export const defaultSearchSettings: SearchSettings = {
  query: "",
  sort: "relevance",
  read_aloud_fields: ["last_author", "journal", "pub_date"],
  default_swipe_behavior: "not_interested",
  speed: 1.1,
};
