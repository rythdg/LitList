/**
 * Hand-written fixture data for Task 2B's presentational screens.
 *
 * Cross-referencing the same PMIDs as fixtures/pubmed/*.json (Task 0.3)
 * so this corpus lines up with what the rest of the project uses for the
 * same edge cases: 38279812 (normal), 38279813 (retracted, no DOI),
 * 37000001 (non-English / narration-unavailable).
 */
import type {
  AbstractSegment,
  Paper,
  QueueItem,
  SearchSettings,
} from "./types";

export const paperNormal: Paper = {
  pmid: "38279812",
  title:
    "Effects of early intervention on outcomes in a mixed-methods cohort study",
  authors: [
    { first_name: "Sofia", last_name: "Alvarez" },
    { first_name: "Wei", last_name: "Chen" },
  ],
  last_author: { first_name: "Wei", last_name: "Chen" },
  journal: "Journal of Applied Clinical Research",
  pub_date: "2024 Feb",
  doi: "10.1234/jacr.2024.001812",
  display_abstract:
    "Results are shown in Fig. 2. Sample sizes varied widely across the six included cohorts. As shown by Smith et al. in a prior cohort, early intervention improved outcomes.",
  citation_count: 12,
  publication_types: ["Journal Article"],
};

export const paperNextUp: Paper = {
  pmid: "37000001",
  title: "Temporal Coding in Cortical Microcircuits During Active Sensing",
  authors: [{ first_name: "Legacy Study", last_name: "Group" }],
  last_author: null,
  journal: "Legacy Medical Bulletin",
  pub_date: "1998",
  doi: null,
  display_abstract:
    "Cette etude retrospective examine une cohorte historique sans traduction anglaise disponible.",
  citation_count: null,
  publication_types: ["Journal Article"],
};

export const paperRetracted: Paper = {
  pmid: "38279813",
  title: "A retrospective analysis of adverse events (no DOI on record)",
  authors: [{ first_name: "Li", last_name: "Chen" }],
  last_author: { first_name: "Li", last_name: "Chen" },
  journal: "International Review of Medicine",
  pub_date: "2023 Nov",
  doi: null,
  display_abstract:
    "This article has been retracted by the publisher. Findings should not be relied upon.",
  citation_count: 3,
  publication_types: ["Retracted Publication", "Journal Article"],
};

export const mockQueue: QueueItem[] = [
  { paper: paperNormal, decision: "pending" },
  { paper: paperNextUp, decision: "pending" },
  { paper: paperRetracted, decision: "pending" },
];

export const mockSavedItems: QueueItem[] = [
  { paper: paperNormal, decision: "interested" },
  { paper: paperNextUp, decision: "interested" },
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
  read_aloud_fields: {
    last_author: true,
    all_authors: false,
    journal: true,
    pub_date: true,
  },
  default_swipe_behavior: "not_interested",
  speed: 1.1,
};
